/* TCC runtime library. 
   Parts of this code are (c) 2002 Fabrice Bellard 

   Copyright (C) 1987, 1988, 1992, 1994, 1995 Free Software Foundation, Inc.

This file is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation; either version 2, or (at your option) any
later version.

In addition to the permissions in the GNU General Public License, the
Free Software Foundation gives you unlimited permission to link the
compiled version of this file into combinations with other programs,
and to distribute those combinations without any restriction coming
from the use of this file.  (The General Public License restrictions
do apply in other respects; for example, they cover modification of
the file, and distribution when not linked into a combine
executable.)

This file is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; see the file COPYING.  If not, write to
the Free Software Foundation, 59 Temple Place - Suite 330,
Boston, MA 02111-1307, USA.  
*/

#define W_TYPE_SIZE   32
#define BITS_PER_UNIT 8

typedef int Wtype;
typedef unsigned int UWtype;
typedef unsigned int USItype;
typedef long long DWtype;
typedef unsigned long long UDWtype;

struct DWstruct {
    Wtype low, high;
};

typedef union
{
  struct DWstruct s;
  DWtype ll;
} DWunion;

typedef long double XFtype;
#define WORD_SIZE (sizeof (Wtype) * BITS_PER_UNIT)
#define HIGH_WORD_COEFF (((UDWtype) 1) << WORD_SIZE)

/* the following deal with IEEE single-precision numbers */
#define EXCESS		126
#define SIGNBIT		0x80000000
#define HIDDEN		(1 << 23)
#define SIGN(fp)	((fp) & SIGNBIT)
#define EXP(fp)		(((fp) >> 23) & 0xFF)
#define MANT(fp)	(((fp) & 0x7FFFFF) | HIDDEN)
#define PACK(s,e,m)	((s) | ((e) << 23) | (m))

/* the following deal with IEEE double-precision numbers */
#define EXCESSD		1022
#define HIDDEND		(1 << 20)
#define EXPD(fp)	(((fp.l.upper) >> 20) & 0x7FF)
#define SIGND(fp)	((fp.l.upper) & SIGNBIT)
#define MANTD(fp)	(((((fp.l.upper) & 0xFFFFF) | HIDDEND) << 10) | \
				(fp.l.lower >> 22))
#define HIDDEND_LL	((long long)1 << 52)
#define MANTD_LL(fp)	((fp.ll & (HIDDEND_LL-1)) | HIDDEND_LL)
#define PACKD_LL(s,e,m)	(((long long)((s)+((e)<<20))<<32)|(m))

/* the following deal with x86 long double-precision numbers */
#define EXCESSLD	16382
#define EXPLD(fp)	(fp.l.upper & 0x7fff)
#define SIGNLD(fp)	((fp.l.upper) & 0x8000)

/* only for x86 */
union ldouble_long {
    long double ld;
    struct {
        unsigned long long lower;
        unsigned short upper;
    } l;
};

union double_long {
    double d;
#if 1
    struct {
        unsigned int lower;
        int upper;
    } l;
#else
    struct {
        int upper;
        unsigned int lower;
    } l;
#endif
    long long ll;
};

union float_long {
    float f;
    unsigned int l;
};

/* XXX: we don't support several builtin supports for now */
#if defined __i386__

/* XXX: use gcc/tcc intrinsic ? */
#define sub_ddmmss(sh, sl, ah, al, bh, bl) \
  __asm__ ("subl %5,%1\n\tsbbl %3,%0"					\
	   : "=r" ((USItype) (sh)),					\
	     "=&r" ((USItype) (sl))					\
	   : "0" ((USItype) (ah)),					\
	     "g" ((USItype) (bh)),					\
	     "1" ((USItype) (al)),					\
	     "g" ((USItype) (bl)))
#define umul_ppmm(w1, w0, u, v) \
  __asm__ ("mull %3"							\
	   : "=a" ((USItype) (w0)),					\
	     "=d" ((USItype) (w1))					\
	   : "%0" ((USItype) (u)),					\
	     "rm" ((USItype) (v)))
#define udiv_qrnnd(q, r, n1, n0, dv) \
  __asm__ ("divl %4"							\
	   : "=a" ((USItype) (q)),					\
	     "=d" ((USItype) (r))					\
	   : "0" ((USItype) (n0)),					\
	     "1" ((USItype) (n1)),					\
	     "rm" ((USItype) (dv)))
#define count_leading_zeros(count, x) \
  do {									\
    USItype __cbtmp;							\
    __asm__ ("bsrl %1,%0"						\
	     : "=r" (__cbtmp) : "rm" ((USItype) (x)));			\
    (count) = __cbtmp ^ 31;						\
  } while (0)

/* most of this code is taken from libgcc2.c from gcc */

static UDWtype __udivmoddi4 (UDWtype n, UDWtype d, UDWtype *rp)
{
  DWunion ww;
  DWunion nn, dd;
  DWunion rr;
  UWtype d0, d1, n0, n1, n2;
  UWtype q0, q1;
  UWtype b, bm;

  nn.ll = n;
  dd.ll = d;

  d0 = dd.s.low;
  d1 = dd.s.high;
  n0 = nn.s.low;
  n1 = nn.s.high;

#if !defined(UDIV_NEEDS_NORMALIZATION)
  if (d1 == 0)
    {
      if (d0 > n1)
	{
	  /* 0q = nn / 0D */

	  udiv_qrnnd (q0, n0, n1, n0, d0);
	  q1 = 0;

	  /* Remainder in n0.  */
	}
      else
	{
	  /* qq = NN / 0d */

	  if (d0 == 0)
	    d0 = 1 / d0;	/* Divide intentionally by zero.  */

	  udiv_qrnnd (q1, n1, 0, n1, d0);
	  udiv_qrnnd (q0, n0, n1, n0, d0);

	  /* Remainder in n0.  */
	}

      if (rp != 0)
	{
	  rr.s.low = n0;
	  rr.s.high = 0;
	  *rp = rr.ll;
	}
    }

#else /* UDIV_NEEDS_NORMALIZATION */

  if (d1 == 0)
    {
      if (d0 > n1)
	{
	  /* 0q = nn / 0D */

	  count_leading_zeros (bm, d0);

	  if (bm != 0)
	    {
	      /* Normalize, i.e. make the most significant bit of the
		 denominator set.  */

	      d0 = d0 << bm;
	      n1 = (n1 << bm) | (n0 >> (W_TYPE_SIZE - bm));
	      n0 = n0 << bm;
	    }

	  udiv_qrnnd (q0, n0, n1, n0, d0);
	  q1 = 0;

	  /* Remainder in n0 >> bm.  */
	}
      else
	{
	  /* qq = NN / 0d */

	  if (d0 == 0)
	    d0 = 1 / d0;	/* Divide intentionally by zero.  */

	  count_leading_zeros (bm, d0);

	  if (bm == 0)
	    {
	      /* From (n1 >= d0) /\ (the most significant bit of d0 is set),
		 conclude (the most significant bit of n1 is set) /\ (the
		 leading quotient digit q1 = 1).

		 This special case is necessary, not an optimization.
		 (Shifts counts of W_TYPE_SIZE are undefined.)  */

	      n1 -= d0;
	      q1 = 1;
	    }
	  else
	    {
	      /* Normalize.  */

	      b = W_TYPE_SIZE - bm;

	      d0 = d0 << bm;
	      n2 = n1 >> b;
	      n1 = (n1 << bm) | (n0 >> b);
	      n0 = n0 << bm;

	      udiv_qrnnd (q1, n1, n2, n1, d0);
	    }

	  /* n1 != d0...  */

	  udiv_qrnnd (q0, n0, n1, n0, d0);

	  /* Remainder in n0 >> bm.  */
	}

      if (rp != 0)
	{
	  rr.s.low = n0 >> bm;
	  rr.s.high = 0;
	  *rp = rr.ll;
	}
    }
#endif /* UDIV_NEEDS_NORMALIZATION */

  else
    {
      if (d1 > n1)
	{
	  /* 00 = nn / DD */

	  q0 = 0;
	  q1 = 0;

	  /* Remainder in n1n0.  */
	  if (rp != 0)
	    {
	      rr.s.low = n0;
	      rr.s.high = n1;
	      *rp = rr.ll;
	    }
	}
      else
	{
	  /* 0q = NN / dd */

	  count_leading_zeros (bm, d1);
	  if (bm == 0)
	    {
	      /* From (n1 >= d1) /\ (the most significant bit of d1 is set),
		 conclude (the most significant bit of n1 is set) /\ (the
		 quotient digit q0 = 0 or 1).

		 This special case is necessary, not an optimization.  */

	      /* The condition on the next line takes advantage of that
		 n1 >= d1 (true due to program flow).  */
	      if (n1 > d1 || n0 >= d0)
		{
		  q0 = 1;
		  sub_ddmmss (n1, n0, n1, n0, d1, d0);
		}
	      else
		q0 = 0;

	      q1 = 0;

	      if (rp != 0)
		{
		  rr.s.low = n0;
		  rr.s.high = n1;
		  *rp = rr.ll;
		}
	    }
	  else
	    {
	      UWtype m1, m0;
	      /* Normalize.  */

	      b = W_TYPE_SIZE - bm;

	      d1 = (d1 << bm) | (d0 >> b);
	      d0 = d0 << bm;
	      n2 = n1 >> b;
	      n1 = (n1 << bm) | (n0 >> b);
	      n0 = n0 << bm;

	      udiv_qrnnd (q0, n1, n2, n1, d1);
	      umul_ppmm (m1, m0, q0, d0);

	      if (m1 > n1 || (m1 == n1 && m0 > n0))
		{
		  q0--;
		  sub_ddmmss (m1, m0, m1, m0, d1, d0);
		}

	      q1 = 0;

	      /* Remainder in (n1n0 - m1m0) >> bm.  */
	      if (rp != 0)
		{
		  sub_ddmmss (n1, n0, n1, n0, m1, m0);
		  rr.s.low = (n1 << b) | (n0 >> bm);
		  rr.s.high = n1 >> bm;
		  *rp = rr.ll;
		}
	    }
	}
    }

  ww.s.low = q0;
  ww.s.high = q1;
  return ww.ll;
}

#define __negdi2(a) (-(a))

long long __divdi3(long long u, long long v)
{
    int c = 0;
    DWunion uu, vv;
    DWtype w;
    
    uu.ll = u;
    vv.ll = v;
    
    if (uu.s.high < 0) {
        c = ~c;
        uu.ll = __negdi2 (uu.ll);
    }
    if (vv.s.high < 0) {
        c = ~c;
        vv.ll = __negdi2 (vv.ll);
    }
    w = __udivmoddi4 (uu.ll, vv.ll, (UDWtype *) 0);
    if (c)
        w = __negdi2 (w);
    return w;
}

long long __moddi3(long long u, long long v)
{
    int c = 0;
    DWunion uu, vv;
    DWtype w;
    
    uu.ll = u;
    vv.ll = v;
    
    if (uu.s.high < 0) {
        c = ~c;
        uu.ll = __negdi2 (uu.ll);
    }
    if (vv.s.high < 0)
        vv.ll = __negdi2 (vv.ll);
    
    __udivmoddi4 (uu.ll, vv.ll, (UDWtype *) &w);
    if (c)
        w = __negdi2 (w);
    return w;
}

unsigned long long __udivdi3(unsigned long long u, unsigned long long v)
{
    return __udivmoddi4 (u, v, (UDWtype *) 0);
}

unsigned long long __umoddi3(unsigned long long u, unsigned long long v)
{
    UDWtype w;
    
    __udivmoddi4 (u, v, &w);
    return w;
}

/* XXX: fix tcc's code generator to do this instead */
long long __ashrdi3(long long a, int b)
{
#ifdef __TINYC__
    DWunion u;
    u.ll = a;
    if (b >= 32) {
        u.s.low = u.s.high >> (b - 32);
        u.s.high = u.s.high >> 31;
    } else if (b != 0) {
        u.s.low = ((unsigned)u.s.low >> b) | ((unsigned)u.s.high << (32 - b));
        u.s.high = u.s.high >> b;
    }
    return u.ll;
#else
    return a >> b;
#endif
}

/* XXX: fix tcc's code generator to do this instead */
unsigned long long __lshrdi3(unsigned long long a, int b)
{
#ifdef __TINYC__
    DWunion u;
    u.ll = a;
    if (b >= 32) {
        u.s.low = (unsigned)u.s.high >> (b - 32);
        u.s.high = 0;
    } else if (b != 0) {
        u.s.low = ((unsigned)u.s.low >> b) | ((unsigned)u.s.high << (32 - b));
        u.s.high = (unsigned)u.s.high >> b;
    }
    return u.ll;
#else
    return a >> b;
#endif
}

/* XXX: fix tcc's code generator to do this instead */
long long __ashldi3(long long a, int b)
{
#ifdef __TINYC__
    DWunion u;
    u.ll = a;
    if (b >= 32) {
        u.s.high = (unsigned)u.s.low << (b - 32);
        u.s.low = 0;
    } else if (b != 0) {
        u.s.high = ((unsigned)u.s.high << b) | ((unsigned)u.s.low >> (32 - b));
        u.s.low = (unsigned)u.s.low << b;
    }
    return u.ll;
#else
    return a << b;
#endif
}

#endif /* __i386__ */

/* XXX: fix tcc's code generator to do this instead */
float __floatundisf(unsigned long long a)
{
    DWunion uu; 
    XFtype r;

    uu.ll = a;
    if (uu.s.high >= 0) {
        return (float)uu.ll;
    } else {
        r = (XFtype)uu.ll;
        r += 18446744073709551616.0;
        return (float)r;
    }
}

double __floatundidf(unsigned long long a)
{
    DWunion uu; 
    XFtype r;

    uu.ll = a;
    if (uu.s.high >= 0) {
        return (double)uu.ll;
    } else {
        r = (XFtype)uu.ll;
        r += 18446744073709551616.0;
        return (double)r;
    }
}

long double __floatundixf(unsigned long long a)
{
    DWunion uu; 
    XFtype r;

    uu.ll = a;
    if (uu.s.high >= 0) {
        return (long double)uu.ll;
    } else {
        r = (XFtype)uu.ll;
        r += 18446744073709551616.0;
        return (long double)r;
    }
}

unsigned long long __fixunssfdi (float a1)
{
    register union float_long fl1;
    register int exp;
    register unsigned long long l;

    fl1.f = a1;

    if (fl1.l == 0)
	return (0);

    exp = EXP (fl1.l) - EXCESS - 24;
    l = MANT(fl1.l);

    if (exp >= 41)
        return 1ULL << 63;
    else if (exp >= 0)
        l <<= exp;
    else if (exp >= -23)
        l >>= -exp;
    else
	return 0;
    if (SIGN(fl1.l))
        l = (unsigned long long)-l;
    return l;
}

long long __fixsfdi (float a1)
{
    long long ret; int s;
    ret = __fixunssfdi((s = a1 >= 0) ? a1 : -a1);
    return s ? ret : -ret;
}

unsigned long long __fixunsdfdi (double a1)
{
    register union double_long dl1;
    register int exp;
    register unsigned long long l;

    dl1.d = a1;

    if (dl1.ll == 0)
	return (0);

    exp = EXPD (dl1) - EXCESSD - 53;
    l = MANTD_LL(dl1);

    if (exp >= 12)
        return 1ULL << 63; /* overflow result (like gcc, somewhat) */
    else if (exp >= 0)
        l <<= exp;
    else if (exp >= -52)
        l >>= -exp;
    else
        return 0;
    if (SIGND(dl1))
        l = (unsigned long long)-l;
    return l;
}

long long __fixdfdi (double a1)
{
    long long ret; int s;
    ret = __fixunsdfdi((s = a1 >= 0) ? a1 : -a1);
    return s ? ret : -ret;
}

#ifndef __arm__
unsigned long long __fixunsxfdi (long double a1)
{
    register union ldouble_long dl1;
    register int exp;
    register unsigned long long l;

    dl1.ld = a1;

    if (dl1.l.lower == 0 && dl1.l.upper == 0)
	return (0);

    exp = EXPLD (dl1) - EXCESSLD - 64;
    l = dl1.l.lower;
    if (exp > 0)
	return 1ULL << 63;
    if (exp < -63)
        return 0;
    l >>= -exp;
    if (SIGNLD(dl1))
        l = (unsigned long long)-l;
    return l;
}

long long __fixxfdi (long double a1)
{
    long long ret; int s;
    ret = __fixunsxfdi((s = a1 >= 0) ? a1 : -a1);
    return s ? ret : -ret;
}
#endif /* !ARM */

/* _BitInt wide helpers (F44): the value operations for the
   memory-resident _BitInt form (widths 65..128).  A value is two
   unsigned long long limbs, normalized: for a signed width the
   bits above the width are copies of the sign bit; for an
   unsigned width they are zero.  Plain C only -- this file is
   compiled by phcc itself, which has no __int128. */

typedef unsigned long long bi_u64;
typedef long long bi_i64;

/* normalize the 128-bit value in r to width w */
static void bi128_norm(bi_u64 *r, int w, int un)
{
    if (w >= 128)
        return;
    if (un) {
        if (w <= 64) {
            r[0] &= w == 64 ? ~(bi_u64)0 : (((bi_u64)1 << w) - 1);
            r[1] = 0;
        } else {
            r[1] &= ((bi_u64)1 << (w - 64)) - 1;
        }
    } else if (w <= 64) {
        if (w < 64)
            r[0] = (bi_u64)((bi_i64)(r[0] << (64 - w)) >> (64 - w));
        r[1] = (r[0] >> 63) ? ~(bi_u64)0 : 0;
    } else {
        int k = w - 64;
        if (k < 64)
            r[1] = (bi_u64)((bi_i64)(r[1] << (64 - k)) >> (64 - k));
    }
}

void __phcc_bi128_add(bi_u64 *r, const bi_u64 *a, const bi_u64 *b,
                      int w, int un)
{
    bi_u64 lo = a[0] + b[0];
    r[1] = a[1] + b[1] + (lo < a[0]);
    r[0] = lo;
    bi128_norm(r, w, un);
}

void __phcc_bi128_sub(bi_u64 *r, const bi_u64 *a, const bi_u64 *b,
                      int w, int un)
{
    bi_u64 lo = a[0] - b[0];
    r[1] = a[1] - b[1] - (lo > a[0]);
    r[0] = lo;
    bi128_norm(r, w, un);
}

void __phcc_bi128_and(bi_u64 *r, const bi_u64 *a, const bi_u64 *b)
{
    r[0] = a[0] & b[0];
    r[1] = a[1] & b[1];
}

void __phcc_bi128_or(bi_u64 *r, const bi_u64 *a, const bi_u64 *b)
{
    r[0] = a[0] | b[0];
    r[1] = a[1] | b[1];
}

void __phcc_bi128_xor(bi_u64 *r, const bi_u64 *a, const bi_u64 *b)
{
    r[0] = a[0] ^ b[0];
    r[1] = a[1] ^ b[1];
}

void __phcc_bi128_mul(bi_u64 *r, const bi_u64 *a, const bi_u64 *b,
                      int w, int un)
{
    /* 32-bit limb schoolbook, keeping the low 128 bits */
    unsigned int al[4], bl[4];
    bi_u64 acc[4];
    int i, j;
    al[0] = (unsigned int)a[0];
    al[1] = (unsigned int)(a[0] >> 32);
    al[2] = (unsigned int)a[1];
    al[3] = (unsigned int)(a[1] >> 32);
    bl[0] = (unsigned int)b[0];
    bl[1] = (unsigned int)(b[0] >> 32);
    bl[2] = (unsigned int)b[1];
    bl[3] = (unsigned int)(b[1] >> 32);
    acc[0] = acc[1] = acc[2] = acc[3] = 0;
    for (i = 0; i < 4; i++) {
        bi_u64 carry = 0;
        for (j = 0; j + i < 4; j++) {
            bi_u64 cur = acc[i + j] + (bi_u64)al[i] * bl[j] + carry;
            acc[i + j] = (unsigned int)cur;
            carry = cur >> 32;
        }
    }
    r[0] = acc[0] | (acc[1] << 32);
    r[1] = acc[2] | (acc[3] << 32);
    bi128_norm(r, w, un);
}

/* the magnitude of a normalized value; sets *neg for a negative
   signed value (the sign lives in bit 127 of the normalized
   form) */
static void bi128_mag(const bi_u64 *a, int un, bi_u64 *m, int *neg)
{
    m[0] = a[0];
    m[1] = a[1];
    *neg = 0;
    if (!un && (a[1] >> 63)) {
        *neg = 1;
        m[0] = ~a[0] + 1;
        m[1] = ~a[1] + (m[0] == 0);
    }
}

static void bi128_udivmod(const bi_u64 *a, const bi_u64 *b,
                          bi_u64 *q, bi_u64 *r)
{
    int i;
    q[0] = q[1] = 0;
    r[0] = r[1] = 0;
    if (b[0] == 0 && b[1] == 0) {
        /* division by zero is undefined for the caller; keep the
           helper itself from trapping */
        q[0] = q[1] = ~(bi_u64)0;
        r[0] = a[0];
        r[1] = a[1];
        return;
    }
    for (i = 127; i >= 0; i--) {
        r[1] = (r[1] << 1) | (r[0] >> 63);
        r[0] = (r[0] << 1) | ((a[i >> 6] >> (i & 63)) & 1);
        if (r[1] > b[1] || (r[1] == b[1] && r[0] >= b[0])) {
            bi_u64 lo = r[0] - b[0];
            r[1] = r[1] - b[1] - (lo > r[0]);
            r[0] = lo;
            q[i >> 6] |= (bi_u64)1 << (i & 63);
        }
    }
}

void __phcc_bi128_div(bi_u64 *r, const bi_u64 *a, const bi_u64 *b,
                      int w, int un)
{
    bi_u64 ma[2], mb[2], q[2], rem[2];
    int na, nb;
    bi128_mag(a, un, ma, &na);
    bi128_mag(b, un, mb, &nb);
    bi128_udivmod(ma, mb, q, rem);
    if (na != nb) {
        r[0] = ~q[0] + 1;
        r[1] = ~q[1] + (r[0] == 0);
    } else {
        r[0] = q[0];
        r[1] = q[1];
    }
    bi128_norm(r, w, un);
}

void __phcc_bi128_mod(bi_u64 *r, const bi_u64 *a, const bi_u64 *b,
                      int w, int un)
{
    bi_u64 ma[2], mb[2], q[2], rem[2];
    int na, nb;
    bi128_mag(a, un, ma, &na);
    bi128_mag(b, un, mb, &nb);
    bi128_udivmod(ma, mb, q, rem);
    if (na) {
        r[0] = ~rem[0] + 1;
        r[1] = ~rem[1] + (r[0] == 0);
    } else {
        r[0] = rem[0];
        r[1] = rem[1];
    }
    bi128_norm(r, w, un);
}

void __phcc_bi128_shl(bi_u64 *r, const bi_u64 *a, bi_u64 n,
                      int w, int un)
{
    if (n >= 128) {
        r[0] = r[1] = 0;
    } else if (n >= 64) {
        r[1] = a[0] << (n - 64);
        r[0] = 0;
    } else if (n == 0) {
        r[0] = a[0];
        r[1] = a[1];
    } else {
        r[1] = (a[1] << n) | (a[0] >> (64 - n));
        r[0] = a[0] << n;
    }
    bi128_norm(r, w, un);
}

void __phcc_bi128_shr(bi_u64 *r, const bi_u64 *a, bi_u64 n,
                      int w, int un)
{
    bi_u64 fill = (!un && (a[1] >> 63)) ? ~(bi_u64)0 : 0;
    if (n >= 128) {
        r[0] = r[1] = fill;
    } else if (n >= 64) {
        r[0] = un ? (a[1] >> (n - 64))
                  : (bi_u64)((bi_i64)a[1] >> (n - 64));
        r[1] = fill;
    } else if (n == 0) {
        r[0] = a[0];
        r[1] = a[1];
    } else {
        r[0] = (a[0] >> n) | (a[1] << (64 - n));
        r[1] = un ? (a[1] >> n) : (bi_u64)((bi_i64)a[1] >> n);
    }
    bi128_norm(r, w, un);
}

int __phcc_bi128_cmp(const bi_u64 *a, const bi_u64 *b, int w, int un)
{
    (void)w;
    if (!un && (bi_i64)a[1] != (bi_i64)b[1])
        return (bi_i64)a[1] < (bi_i64)b[1] ? -1 : 1;
    if (un && a[1] != b[1])
        return a[1] < b[1] ? -1 : 1;
    if (a[0] != b[0])
        return a[0] < b[0] ? -1 : 1;
    return 0;
}

void __phcc_bi128_cast(bi_u64 *r, const bi_u64 *a,
                       int aw, int aus, int bw, int bus)
{
    /* normalize at the source width (cleans), then at the
       destination width (truncate and re-extend): exactly the
       value conversion */
    bi_u64 v[2];
    v[0] = a[0];
    v[1] = a[1];
    bi128_norm(v, aw, aus);
    r[0] = v[0];
    r[1] = v[1];
    bi128_norm(r, bw, bus);
}

double __phcc_bi128_tod(const bi_u64 *a, int w, int un)
{
    bi_u64 m[2];
    int neg;
    double d;
    (void)w;
    bi128_mag(a, un, m, &neg);
    d = (double)m[1] * 18446744073709551616.0 + (double)m[0];
    return neg ? -d : d;
}

int __phcc_bi128_nonzero(const bi_u64 *a)
{
    return (a[0] | a[1]) != 0;
}
