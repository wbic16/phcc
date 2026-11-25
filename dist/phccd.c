/* phccd - distributed compile worker for phcc.
 *
 * One worker per node. The compiler is libtcc, linked in: a work unit
 * arrives as preprocessed source, is verified against its hash-pinned
 * identity, compiled in-process, and the object is returned with its
 * SHA-256. Nodes are untrusted carriers (the wpm rule): the name asks,
 * the hash decides. A unit whose bytes do not match its identity is
 * rejected, never compiled. There is no local fallback anywhere in
 * this program: it either compiles the unit it was given or reports
 * the failure.
 *
 * Protocol (all integers big-endian, frames length-prefixed):
 *   on connect, worker sends HELLO:
 *     'PHCH' u64 len | compiler_id[32] | u16 ver_len | version bytes
 *   request:
 *     'PHCU' u64 len | unit_id[32] | u16 flags_len | flags |
 *                      u64 src_len | src bytes
 *   response:
 *     'PHCO' u64 len | u8 status | u8 cache_hit | obj_sha256[32] |
 *                      u64 obj_len | obj bytes |
 *                      (status != 0: u16 msg_len | msg instead of obj)
 *
 * unit_id = SHA256("phcc-dist-v1" || compiler_id || flags || 0x00 || src)
 * compiler_id = SHA256 of the worker's own executable image, so a unit
 * is pinned to the exact compiler build that may produce its object.
 *
 * Usage: phccd <port> [cache-dir]
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#include "libtcc.h"

/* ---------------- SHA-256 (FIPS 180-4) ---------------- */

typedef struct {
    uint32_t h[8];
    uint64_t len;
    uint8_t buf[64];
    size_t buflen;
} sha256_ctx;

static const uint32_t sha_k[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};

#define RR(x,n) (((x) >> (n)) | ((x) << (32 - (n))))

static void sha256_block(sha256_ctx *c, const uint8_t *p)
{
    uint32_t w[64];
    int i;
    for (i = 0; i < 16; i++)
        w[i] = ((uint32_t)p[i*4] << 24) | ((uint32_t)p[i*4+1] << 16) |
               ((uint32_t)p[i*4+2] << 8) | (uint32_t)p[i*4+3];
    for (i = 16; i < 64; i++) {
        uint32_t s0 = RR(w[i-15],7) ^ RR(w[i-15],18) ^ (w[i-15] >> 3);
        uint32_t s1 = RR(w[i-2],17) ^ RR(w[i-2],19) ^ (w[i-2] >> 10);
        w[i] = w[i-16] + s0 + w[i-7] + s1;
    }
    uint32_t a=c->h[0],b=c->h[1],d=c->h[3],e=c->h[4],f=c->h[5],g=c->h[6],h=c->h[7],cc=c->h[2];
    for (i = 0; i < 64; i++) {
        uint32_t S1 = RR(e,6) ^ RR(e,11) ^ RR(e,25);
        uint32_t ch = (e & f) ^ (~e & g);
        uint32_t t1 = h + S1 + ch + sha_k[i] + w[i];
        uint32_t S0 = RR(a,2) ^ RR(a,13) ^ RR(a,22);
        uint32_t mj = (a & b) ^ (a & cc) ^ (b & cc);
        uint32_t t2 = S0 + mj;
        h=g; g=f; f=e; e=d+t1; d=cc; cc=b; b=a; a=t1+t2;
    }
    c->h[0]+=a; c->h[1]+=b; c->h[2]+=cc; c->h[3]+=d;
    c->h[4]+=e; c->h[5]+=f; c->h[6]+=g; c->h[7]+=h;
}

static void sha256_init(sha256_ctx *c)
{
    static const uint32_t h0[8] = {
        0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
        0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19
    };
    memcpy(c->h, h0, sizeof h0);
    c->len = 0;
    c->buflen = 0;
}

static void sha256_update(sha256_ctx *c, const void *data, size_t n)
{
    const uint8_t *p = (const uint8_t *)data;
    c->len += n;
    while (n) {
        size_t take = 64 - c->buflen;
        if (take > n) take = n;
        memcpy(c->buf + c->buflen, p, take);
        c->buflen += take;
        p += take;
        n -= take;
        if (c->buflen == 64) {
            sha256_block(c, c->buf);
            c->buflen = 0;
        }
    }
}

static void sha256_final(sha256_ctx *c, uint8_t out[32])
{
    uint64_t bits = c->len * 8;
    uint8_t pad = 0x80;
    uint8_t zero = 0;
    uint8_t lenbe[8];
    int i;
    sha256_update(c, &pad, 1);
    while (c->buflen != 56) sha256_update(c, &zero, 1);
    /* buflen == 56, append length directly (bypass update's len count) */
    for (i = 0; i < 8; i++) lenbe[i] = (uint8_t)(bits >> (56 - 8*i));
    memcpy(c->buf + 56, lenbe, 8);
    sha256_block(c, c->buf);
    for (i = 0; i < 8; i++) {
        out[i*4]   = (uint8_t)(c->h[i] >> 24);
        out[i*4+1] = (uint8_t)(c->h[i] >> 16);
        out[i*4+2] = (uint8_t)(c->h[i] >> 8);
        out[i*4+3] = (uint8_t)(c->h[i]);
    }
}

static void sha256(const void *data, size_t n, uint8_t out[32])
{
    sha256_ctx c;
    sha256_init(&c);
    sha256_update(&c, data, n);
    sha256_final(&c, out);
}

static void hex32(const uint8_t h[32], char out[65])
{
    static const char *digits = "0123456789abcdef";
    int i;
    for (i = 0; i < 32; i++) {
        out[i*2] = digits[h[i] >> 4];
        out[i*2+1] = digits[h[i] & 15];
    }
    out[64] = 0;
}

/* ---------------- framing helpers ---------------- */

static int write_all(int fd, const void *buf, size_t n)
{
    const uint8_t *p = (const uint8_t *)buf;
    while (n) {
        ssize_t w = write(fd, p, n);
        if (w < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        p += w;
        n -= (size_t)w;
    }
    return 0;
}

static int read_all(int fd, void *buf, size_t n)
{
    uint8_t *p = (uint8_t *)buf;
    while (n) {
        ssize_t r = read(fd, p, n);
        if (r < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        if (r == 0) return -1;
        p += r;
        n -= (size_t)r;
    }
    return 0;
}

static void put_u64(uint8_t *p, uint64_t v)
{
    int i;
    for (i = 0; i < 8; i++) p[i] = (uint8_t)(v >> (56 - 8*i));
}

static uint64_t get_u64(const uint8_t *p)
{
    uint64_t v = 0;
    int i;
    for (i = 0; i < 8; i++) v = (v << 8) | p[i];
    return v;
}

static void put_u16(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)(v >> 8);
    p[1] = (uint8_t)v;
}

static uint16_t get_u16(const uint8_t *p)
{
    return (uint16_t)((p[0] << 8) | p[1]);
}

/* ---------------- worker ---------------- */

static uint8_t compiler_id[32];
static char cache_dir[512] = "./phccd-cache";

static char errbuf[4096];
static size_t errlen;

static void on_tcc_error(void *opaque, const char *msg)
{
    size_t m = strlen(msg);
    (void)opaque;
    if (errlen + m + 2 < sizeof errbuf) {
        memcpy(errbuf + errlen, msg, m);
        errlen += m;
        errbuf[errlen++] = '\n';
        errbuf[errlen] = 0;
    }
}

static int send_response(int fd, int status, int cache_hit,
                         const uint8_t obj_hash[32],
                         const uint8_t *obj, uint64_t obj_len,
                         const char *msg)
{
    uint64_t payload = 1 + 1 + 32 + 8 + (status == 0 ? obj_len
                                        : 2 + (uint64_t)strlen(msg));
    uint8_t *frame = malloc(12 + payload);
    uint8_t *p;
    if (!frame) return -1;
    memcpy(frame, "PHCO", 4);
    put_u64(frame + 4, payload);
    p = frame + 12;
    *p++ = (uint8_t)status;
    *p++ = (uint8_t)cache_hit;
    memcpy(p, obj_hash, 32); p += 32;
    put_u64(p, status == 0 ? obj_len : 0); p += 8;
    if (status == 0) {
        memcpy(p, obj, (size_t)obj_len);
    } else {
        size_t m = strlen(msg);
        put_u16(p, (uint16_t)m); p += 2;
        memcpy(p, msg, m);
    }
    int rc = write_all(fd, frame, 12 + payload);
    free(frame);
    return rc;
}

static void handle_unit(int fd)
{
    uint8_t hdr[12];
    uint8_t *payload = NULL;
    uint8_t zero_hash[32] = {0};
    if (read_all(fd, hdr, 12) < 0) return;
    if (memcmp(hdr, "PHCU", 4) != 0) return;
    uint64_t plen = get_u64(hdr + 4);
    if (plen > (256u << 20)) return;
    payload = malloc(plen ? plen : 1);
    if (!payload) return;
    if (read_all(fd, payload, plen) < 0) goto out;

    const uint8_t *p = payload;
    const uint8_t *end = payload + plen;
    if (p + 32 + 2 > end) goto out;
    const uint8_t *unit_id = p; p += 32;
    uint16_t flags_len = get_u16(p); p += 2;
    if (p + flags_len + 8 > end) goto out;
    const uint8_t *flags = p; p += flags_len;
    uint64_t src_len = get_u64(p); p += 8;
    if (p + src_len > end || src_len > (64u << 20)) goto out;
    const uint8_t *src = p;

    /* Verify the unit's identity before touching the compiler. */
    {
        sha256_ctx c;
        uint8_t digest[32];
        uint8_t z = 0;
        sha256_init(&c);
        sha256_update(&c, "phcc-dist-v1", 12);
        sha256_update(&c, compiler_id, 32);
        sha256_update(&c, flags, flags_len);
        sha256_update(&c, &z, 1);
        sha256_update(&c, src, (size_t)src_len);
        sha256_final(&c, digest);
        if (memcmp(digest, unit_id, 32) != 0) {
            send_response(fd, 2, 0, zero_hash, NULL, 0,
                          "unit hash mismatch: bytes do not match identity");
            goto out;
        }
    }

    char idhex[65];
    hex32(unit_id, idhex);

    /* Cache: identity is the hash, so a hit is safe by construction. */
    char cache_path[600];
    snprintf(cache_path, sizeof cache_path, "%s/%s.o", cache_dir, idhex);
    {
        int cfd = open(cache_path, O_RDONLY);
        if (cfd >= 0) {
            struct stat st;
            if (fstat(cfd, &st) == 0 && st.st_size > 0) {
                uint8_t *obj = malloc((size_t)st.st_size);
                if (obj && read_all(cfd, obj, (size_t)st.st_size) == 0) {
                    uint8_t oh[32];
                    sha256(obj, (size_t)st.st_size, oh);
                    send_response(fd, 0, 1, oh, obj, (uint64_t)st.st_size, NULL);
                    free(obj);
                    close(cfd);
                    goto out;
                }
                free(obj);
            }
            close(cfd);
        }
    }

    /* Compile in-process with libtcc. The unit is written to a file
     * named by its own identity (<unit_id>.i) in a scratch dir and
     * compiled under that name: the object records its source name,
     * so the recorded name is canonicalized to the unit hash — the
     * same name the driver's local compile uses, which is what makes
     * byte-identity between node and local objects well-defined. */
    {
        char work_dir[600];
        snprintf(work_dir, sizeof work_dir, "%s/.work-%d",
                 cache_dir, (int)getpid());
        mkdir(work_dir, 0755);
        char src_name[80];
        snprintf(src_name, sizeof src_name, "%s.i", idhex);
        char src_path[700];
        snprintf(src_path, sizeof src_path, "%s/%s", work_dir, src_name);
        int sfd = open(src_path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (sfd < 0 || write_all(sfd, src, (size_t)src_len) != 0) {
            if (sfd >= 0) close(sfd);
            send_response(fd, 3, 0, zero_hash, NULL, 0,
                          "unit scratch write failed");
            goto out;
        }
        close(sfd);

        TCCState *s = tcc_new();
        if (!s) {
            unlink(src_path);
            send_response(fd, 3, 0, zero_hash, NULL, 0, "tcc_new failed");
            goto out;
        }
        errlen = 0; errbuf[0] = 0;
        tcc_set_error_func(s, NULL, on_tcc_error);
        tcc_set_output_type(s, TCC_OUTPUT_OBJ);
        if (flags_len > 0) {
            char *f = malloc(flags_len + 1);
            memcpy(f, flags, flags_len);
            f[flags_len] = 0;
            tcc_set_options(s, f);
            free(f);
        }
        char obj_name[80];
        snprintf(obj_name, sizeof obj_name, "%s.o", idhex);
        char tmp_path[700];
        snprintf(tmp_path, sizeof tmp_path, "%s/%s", work_dir, obj_name);
        char cwd[512];
        int rc = -1;
        if (getcwd(cwd, sizeof cwd) != NULL && chdir(work_dir) == 0) {
            rc = tcc_add_file(s, src_name);
            if (rc == 0)
                rc = tcc_output_file(s, obj_name);
            if (chdir(cwd) != 0) { /* scratch cleanup below still applies */ }
        }
        tcc_delete(s);
        unlink(src_path);
        if (rc != 0) {
            unlink(tmp_path);
            rmdir(work_dir);
            send_response(fd, 1, 0, zero_hash, NULL, 0,
                          errlen ? errbuf : "compilation failed");
            goto out;
        }
        int ofd = open(tmp_path, O_RDONLY);
        struct stat st;
        if (ofd < 0 || fstat(ofd, &st) != 0) {
            if (ofd >= 0) close(ofd);
            unlink(tmp_path);
            send_response(fd, 3, 0, zero_hash, NULL, 0, "object unreadable");
            goto out;
        }
        uint8_t *obj = malloc((size_t)st.st_size ? (size_t)st.st_size : 1);
        if (read_all(ofd, obj, (size_t)st.st_size) != 0) {
            close(ofd);
            free(obj);
            unlink(tmp_path);
            send_response(fd, 3, 0, zero_hash, NULL, 0, "object read failed");
            goto out;
        }
        close(ofd);
        rename(tmp_path, cache_path);
        rmdir(work_dir);
        uint8_t oh[32];
        sha256(obj, (size_t)st.st_size, oh);
        send_response(fd, 0, 0, oh, obj, (uint64_t)st.st_size, NULL);
        free(obj);
    }
out:
    free(payload);
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: phccd <port> [cache-dir]\n");
        return 1;
    }
    int port = atoi(argv[1]);
    if (argc > 2)
        snprintf(cache_dir, sizeof cache_dir, "%s", argv[2]);
    mkdir(cache_dir, 0755);

    /* compiler_id = SHA-256 of our own executable image. */
    {
        int fd = open("/proc/self/exe", O_RDONLY);
        if (fd < 0) { perror("open /proc/self/exe"); return 1; }
        sha256_ctx c;
        uint8_t buf[65536];
        ssize_t r;
        sha256_init(&c);
        while ((r = read(fd, buf, sizeof buf)) > 0)
            sha256_update(&c, buf, (size_t)r);
        close(fd);
        sha256_final(&c, compiler_id);
    }
    char idhex[65];
    hex32(compiler_id, idhex);
    fprintf(stderr, "phccd: compiler_id=%s cache=%s port=%d\n",
            idhex, cache_dir, port);

    signal(SIGCHLD, SIG_IGN);
    signal(SIGPIPE, SIG_IGN);

    int ls = socket(AF_INET, SOCK_STREAM, 0);
    if (ls < 0) { perror("socket"); return 1; }
    int one = 1;
    setsockopt(ls, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof addr);
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons((uint16_t)port);
    if (bind(ls, (struct sockaddr *)&addr, sizeof addr) < 0) {
        perror("bind");
        return 1;
    }
    if (listen(ls, 64) < 0) { perror("listen"); return 1; }

    for (;;) {
        int fd = accept(ls, NULL, NULL);
        if (fd < 0) {
            if (errno == EINTR) continue;
            perror("accept");
            continue;
        }
        pid_t pid = fork();
        if (pid == 0) {
            close(ls);
            /* HELLO */
            const char *ver = "phcc-dist-v1";
            uint16_t vl = (uint16_t)strlen(ver);
            uint64_t payload = 32 + 2 + vl;
            uint8_t hdr[12];
            memcpy(hdr, "PHCH", 4);
            put_u64(hdr + 4, payload);
            if (write_all(fd, hdr, 12) == 0 &&
                write_all(fd, compiler_id, 32) == 0) {
                uint8_t vb[2];
                put_u16(vb, vl);
                if (write_all(fd, vb, 2) == 0)
                    write_all(fd, ver, vl);
            }
            handle_unit(fd);
            close(fd);
            _exit(0);
        }
        close(fd);
    }
    return 0;
}
