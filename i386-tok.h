/* ------------------------------------------------------------------ */
/* WARNING: relative order of tokens is important. */

#define DEF_BWL(x) \
 DEF(TOK_ASM_ ## x ## b, #x "b") \
 DEF(TOK_ASM_ ## x ## w, #x "w") \
 DEF(TOK_ASM_ ## x ## l, #x "l") \
 DEF(TOK_ASM_ ## x, #x)
#define DEF_WL(x) \
 DEF(TOK_ASM_ ## x ## w, #x "w") \
 DEF(TOK_ASM_ ## x ## l, #x "l") \
 DEF(TOK_ASM_ ## x, #x)
#ifdef TCC_TARGET_X86_64
# define DEF_BWLQ(x) \
 DEF(TOK_ASM_ ## x ## b, #x "b") \
 DEF(TOK_ASM_ ## x ## w, #x "w") \
 DEF(TOK_ASM_ ## x ## l, #x "l") \
 DEF(TOK_ASM_ ## x ## q, #x "q") \
 DEF(TOK_ASM_ ## x, #x)
# define DEF_WLQ(x) \
 DEF(TOK_ASM_ ## x ## w, #x "w") \
 DEF(TOK_ASM_ ## x ## l, #x "l") \
 DEF(TOK_ASM_ ## x ## q, #x "q") \
 DEF(TOK_ASM_ ## x, #x)
# define DEF_BWLX DEF_BWLQ
# define DEF_WLX DEF_WLQ
/* number of sizes + 1 */
# define NBWLX 5
#else
# define DEF_BWLX DEF_BWL
# define DEF_WLX DEF_WL
/* number of sizes + 1 */
# define NBWLX 4
#endif

#define DEF_FP1(x) \
 DEF(TOK_ASM_ ## f ## x ## s, "f" #x "s") \
 DEF(TOK_ASM_ ## fi ## x ## l, "fi" #x "l") \
 DEF(TOK_ASM_ ## f ## x ## l, "f" #x "l") \
 DEF(TOK_ASM_ ## fi ## x ## s, "fi" #x "s")

#define DEF_FP(x) \
 DEF(TOK_ASM_ ## f ## x, "f" #x ) \
 DEF(TOK_ASM_ ## f ## x ## p, "f" #x "p") \
 DEF_FP1(x)

#define DEF_ASMTEST(x,suffix) \
 DEF_ASM(x ## o ## suffix) \
 DEF_ASM(x ## no ## suffix) \
 DEF_ASM(x ## b ## suffix) \
 DEF_ASM(x ## c ## suffix) \
 DEF_ASM(x ## nae ## suffix) \
 DEF_ASM(x ## nb ## suffix) \
 DEF_ASM(x ## nc ## suffix) \
 DEF_ASM(x ## ae ## suffix) \
 DEF_ASM(x ## e ## suffix) \
 DEF_ASM(x ## z ## suffix) \
 DEF_ASM(x ## ne ## suffix) \
 DEF_ASM(x ## nz ## suffix) \
 DEF_ASM(x ## be ## suffix) \
 DEF_ASM(x ## na ## suffix) \
 DEF_ASM(x ## nbe ## suffix) \
 DEF_ASM(x ## a ## suffix) \
 DEF_ASM(x ## s ## suffix) \
 DEF_ASM(x ## ns ## suffix) \
 DEF_ASM(x ## p ## suffix) \
 DEF_ASM(x ## pe ## suffix) \
 DEF_ASM(x ## np ## suffix) \
 DEF_ASM(x ## po ## suffix) \
 DEF_ASM(x ## l ## suffix) \
 DEF_ASM(x ## nge ## suffix) \
 DEF_ASM(x ## nl ## suffix) \
 DEF_ASM(x ## ge ## suffix) \
 DEF_ASM(x ## le ## suffix) \
 DEF_ASM(x ## ng ## suffix) \
 DEF_ASM(x ## nle ## suffix) \
 DEF_ASM(x ## g ## suffix)

/* ------------------------------------------------------------------ */
/* register */
 DEF_ASM(al)
 DEF_ASM(cl)
 DEF_ASM(dl)
 DEF_ASM(bl)
 DEF_ASM(ah)
 DEF_ASM(ch)
 DEF_ASM(dh)
 DEF_ASM(bh)
 DEF_ASM(ax)
 DEF_ASM(cx)
 DEF_ASM(dx)
 DEF_ASM(bx)
 DEF_ASM(sp)
 DEF_ASM(bp)
 DEF_ASM(si)
 DEF_ASM(di)
 DEF_ASM(eax)
 DEF_ASM(ecx)
 DEF_ASM(edx)
 DEF_ASM(ebx)
 DEF_ASM(esp)
 DEF_ASM(ebp)
 DEF_ASM(esi)
 DEF_ASM(edi)
#ifdef TCC_TARGET_X86_64
 DEF_ASM(rax)
 DEF_ASM(rcx)
 DEF_ASM(rdx)
 DEF_ASM(rbx)
 DEF_ASM(rsp)
 DEF_ASM(rbp)
 DEF_ASM(rsi)
 DEF_ASM(rdi)
#endif
 DEF_ASM(mm0)
 DEF_ASM(mm1)
 DEF_ASM(mm2)
 DEF_ASM(mm3)
 DEF_ASM(mm4)
 DEF_ASM(mm5)
 DEF_ASM(mm6)
 DEF_ASM(mm7)
 DEF_ASM(xmm0)
 DEF_ASM(xmm1)
 DEF_ASM(xmm2)
 DEF_ASM(xmm3)
 DEF_ASM(xmm4)
 DEF_ASM(xmm5)
 DEF_ASM(xmm6)
 DEF_ASM(xmm7)
 DEF_ASM(cr0)
 DEF_ASM(cr1)
 DEF_ASM(cr2)
 DEF_ASM(cr3)
 DEF_ASM(cr4)
 DEF_ASM(cr5)
 DEF_ASM(cr6)
 DEF_ASM(cr7)
 DEF_ASM(tr0)
 DEF_ASM(tr1)
 DEF_ASM(tr2)
 DEF_ASM(tr3)
 DEF_ASM(tr4)
 DEF_ASM(tr5)
 DEF_ASM(tr6)
 DEF_ASM(tr7)
 DEF_ASM(db0)
 DEF_ASM(db1)
 DEF_ASM(db2)
 DEF_ASM(db3)
 DEF_ASM(db4)
 DEF_ASM(db5)
 DEF_ASM(db6)
 DEF_ASM(db7)
 DEF_ASM(dr0)
 DEF_ASM(dr1)
 DEF_ASM(dr2)
 DEF_ASM(dr3)
 DEF_ASM(dr4)
 DEF_ASM(dr5)
 DEF_ASM(dr6)
 DEF_ASM(dr7)
 DEF_ASM(es)
 DEF_ASM(cs)
 DEF_ASM(ss)
 DEF_ASM(ds)
 DEF_ASM(fs)
 DEF_ASM(gs)
 DEF_ASM(st)
 DEF_ASM(rip)

#ifdef TCC_TARGET_X86_64
 /* The four low parts of sp/bp/si/di that exist only on
    x86-64 (encoding aliased to ah,ch,dh,dh when not using REX). */
 DEF_ASM(spl)
 DEF_ASM(bpl)
 DEF_ASM(sil)
 DEF_ASM(dil)
 /* The high SSE registers; these cannot join the contiguous
    al..db7 block above (its reg>>3 class encoding is full), so
    parse_operand recognises them explicitly (F12). */
 DEF_ASM(xmm8)
 DEF_ASM(xmm9)
 DEF_ASM(xmm10)
 DEF_ASM(xmm11)
 DEF_ASM(xmm12)
 DEF_ASM(xmm13)
 DEF_ASM(xmm14)
 DEF_ASM(xmm15)
 DEF_ASM(xmm16)
 DEF_ASM(xmm17)
 DEF_ASM(xmm18)
 DEF_ASM(xmm19)
 DEF_ASM(xmm20)
 DEF_ASM(xmm21)
 DEF_ASM(xmm22)
 DEF_ASM(xmm23)
 DEF_ASM(xmm24)
 DEF_ASM(xmm25)
 DEF_ASM(xmm26)
 DEF_ASM(xmm27)
 DEF_ASM(xmm28)
 DEF_ASM(xmm29)
 DEF_ASM(xmm30)
 DEF_ASM(xmm31)
 DEF_ASM(ymm0)
 DEF_ASM(ymm1)
 DEF_ASM(ymm2)
 DEF_ASM(ymm3)
 DEF_ASM(ymm4)
 DEF_ASM(ymm5)
 DEF_ASM(ymm6)
 DEF_ASM(ymm7)
 DEF_ASM(ymm8)
 DEF_ASM(ymm9)
 DEF_ASM(ymm10)
 DEF_ASM(ymm11)
 DEF_ASM(ymm12)
 DEF_ASM(ymm13)
 DEF_ASM(ymm14)
 DEF_ASM(ymm15)
 DEF_ASM(ymm16)
 DEF_ASM(ymm17)
 DEF_ASM(ymm18)
 DEF_ASM(ymm19)
 DEF_ASM(ymm20)
 DEF_ASM(ymm21)
 DEF_ASM(ymm22)
 DEF_ASM(ymm23)
 DEF_ASM(ymm24)
 DEF_ASM(ymm25)
 DEF_ASM(ymm26)
 DEF_ASM(ymm27)
 DEF_ASM(ymm28)
 DEF_ASM(ymm29)
 DEF_ASM(ymm30)
 DEF_ASM(ymm31)
 DEF_ASM(zmm0)
 DEF_ASM(zmm1)
 DEF_ASM(zmm2)
 DEF_ASM(zmm3)
 DEF_ASM(zmm4)
 DEF_ASM(zmm5)
 DEF_ASM(zmm6)
 DEF_ASM(zmm7)
 DEF_ASM(zmm8)
 DEF_ASM(zmm9)
 DEF_ASM(zmm10)
 DEF_ASM(zmm11)
 DEF_ASM(zmm12)
 DEF_ASM(zmm13)
 DEF_ASM(zmm14)
 DEF_ASM(zmm15)
 DEF_ASM(zmm16)
 DEF_ASM(zmm17)
 DEF_ASM(zmm18)
 DEF_ASM(zmm19)
 DEF_ASM(zmm20)
 DEF_ASM(zmm21)
 DEF_ASM(zmm22)
 DEF_ASM(zmm23)
 DEF_ASM(zmm24)
 DEF_ASM(zmm25)
 DEF_ASM(zmm26)
 DEF_ASM(zmm27)
 DEF_ASM(zmm28)
 DEF_ASM(zmm29)
 DEF_ASM(zmm30)
 DEF_ASM(zmm31)
 DEF_ASM(k0)
 DEF_ASM(k1)
 DEF_ASM(k2)
 DEF_ASM(k3)
 DEF_ASM(k4)
 DEF_ASM(k5)
 DEF_ASM(k6)
 DEF_ASM(k7)
#endif
 /* generic two operands */
 DEF_BWLX(mov)

 DEF_BWLX(add)
 DEF_BWLX(or)
 DEF_BWLX(adc)
 DEF_BWLX(sbb)
 DEF_BWLX(and)
 DEF_BWLX(sub)
 DEF_BWLX(xor)
 DEF_BWLX(cmp)

 /* unary ops */
 DEF_BWLX(inc)
 DEF_BWLX(dec)
 DEF_BWLX(not)
 DEF_BWLX(neg)
 DEF_BWLX(mul)
 DEF_BWLX(imul)
 DEF_BWLX(div)
 DEF_BWLX(idiv)

 DEF_BWLX(xchg)
 DEF_BWLX(test)

 /* shifts */
 DEF_BWLX(rol)
 DEF_BWLX(ror)
 DEF_BWLX(rcl)
 DEF_BWLX(rcr)
 DEF_BWLX(shl)
 DEF_BWLX(shr)
 DEF_BWLX(sar)
 DEF_BWLX(sal)

 DEF_WLX(shld)
 DEF_WLX(shrd)

 DEF_ASM(pushw)
 DEF_ASM(pushl)
#ifdef TCC_TARGET_X86_64
 DEF_ASM(pushq)
#endif
 DEF_ASM(push)

 DEF_ASM(popw)
 DEF_ASM(popl)
#ifdef TCC_TARGET_X86_64
 DEF_ASM(popq)
#endif
 DEF_ASM(pop)

 DEF_BWL(in)
 DEF_BWL(out)

 DEF_WLX(movzb)
 DEF_ASM(movzwl)
 DEF_ASM(movsbw)
 DEF_ASM(movsbl)
 DEF_ASM(movswl)
#ifdef TCC_TARGET_X86_64
 DEF_ASM(movsbq)
 DEF_ASM(movswq)
 DEF_ASM(movzwq)
 DEF_ASM(movslq)
#endif

 DEF_WLX(lea)

 DEF_ASM(les)
 DEF_ASM(lds)
 DEF_ASM(lss)
 DEF_ASM(lfs)
 DEF_ASM(lgs)

 DEF_ASM(call)
 DEF_ASM(jmp)
 DEF_ASM(lcall)
 DEF_ASM(ljmp)

 DEF_ASMTEST(j,)

 DEF_ASMTEST(set,)
 DEF_ASMTEST(set,b)
 DEF_ASMTEST(cmov,)

 DEF_WLX(bsf)
 DEF_WLX(bsr)
 DEF_WLX(bt)
 DEF_WLX(bts)
 DEF_WLX(btr)
 DEF_WLX(btc)
 DEF_WLX(popcnt)
 DEF_WLX(tzcnt)
 DEF_WLX(lzcnt)

 DEF_WLX(lar)
 DEF_WLX(lsl)

 /* generic FP ops */
 DEF_FP(add)
 DEF_FP(mul)

 DEF_ASM(fcom)
 DEF_ASM(fcom_1) /* non existent op, just to have a regular table */
 DEF_FP1(com)

 DEF_FP(comp)
 DEF_FP(sub)
 DEF_FP(subr)
 DEF_FP(div)
 DEF_FP(divr)

 DEF_BWLX(xadd)
 DEF_BWLX(cmpxchg)

 /* string ops */
 DEF_BWLX(cmps)
 DEF_BWLX(scmp)
 DEF_BWL(ins)
 DEF_BWL(outs)
 DEF_BWLX(lods)
 DEF_BWLX(slod)
 DEF_BWLX(movs)
 DEF_BWLX(smov)
 DEF_BWLX(scas)
 DEF_BWLX(ssca)
 DEF_BWLX(stos)
 DEF_BWLX(ssto)

 /* generic asm ops */
#define ALT(x)
#define DEF_ASM_OP0(name, opcode) DEF_ASM(name)
#define DEF_ASM_OP0L(name, opcode, group, instr_type)
#define DEF_ASM_OP1(name, opcode, group, instr_type, op0)
#define DEF_ASM_OP2(name, opcode, group, instr_type, op0, op1)
#define DEF_ASM_OP3(name, opcode, group, instr_type, op0, op1, op2)
#ifdef TCC_TARGET_X86_64
# include "x86_64-asm.h"
#else
# include "i386-asm.h"
#endif

#define ALT(x)
#define DEF_ASM_OP0(name, opcode)
#define DEF_ASM_OP0L(name, opcode, group, instr_type) DEF_ASM(name)
#define DEF_ASM_OP1(name, opcode, group, instr_type, op0) DEF_ASM(name)
#define DEF_ASM_OP2(name, opcode, group, instr_type, op0, op1) DEF_ASM(name)
#define DEF_ASM_OP3(name, opcode, group, instr_type, op0, op1, op2) DEF_ASM(name)
#ifdef TCC_TARGET_X86_64
# include "x86_64-asm.h"
#else
# include "i386-asm.h"
#endif

/* F31: VEX/EVEX register and mnemonic tokens.  The mnemonic tokens
   live after the legacy tables on purpose: nothing in the legacy
   token arithmetic (TOK_ASM_first/last/alllast, op0_codes) moves. */
DEF_ASM(mulx)
DEF_ASM(mulxl)
DEF_ASM(mulxq)
DEF_ASM(vaesenc)
DEF_ASM(vaesenclast)
DEF_ASM(vaesdec)
DEF_ASM(vaesdeclast)
DEF_ASM(vpclmulqdq)
DEF_ASM(vpaddb)
DEF_ASM(vpaddd)
DEF_ASM(vpaddq)
DEF_ASM(vpsubd)
DEF_ASM(vpsubq)
DEF_ASM(vpand)
DEF_ASM(vpandn)
DEF_ASM(vpandd)
DEF_ASM(vpandq)
DEF_ASM(vpor)
DEF_ASM(vporq)
DEF_ASM(vpxor)
DEF_ASM(vpxord)
DEF_ASM(vpxorq)
DEF_ASM(vxorps)
DEF_ASM(vpshufb)
DEF_ASM(vpunpckldq)
DEF_ASM(vpunpckhdq)
DEF_ASM(vpunpcklqdq)
DEF_ASM(vpunpckhqdq)
DEF_ASM(vpcmpeqd)
DEF_ASM(vpcmpgtd)
DEF_ASM(vpcmpeqq)
DEF_ASM(vpcmpgtq)
DEF_ASM(vpcmpq)
DEF_ASM(vpcmpuq)
DEF_ASM(vpmuludq)
DEF_ASM(vpmadd52luq)
DEF_ASM(vpmadd52huq)
DEF_ASM(vpternlogq)
DEF_ASM(vpermd)
DEF_ASM(vpermq)
DEF_ASM(vperm2i128)
DEF_ASM(vpermpd)
DEF_ASM(vpermilps)
DEF_ASM(vpermilpd)
DEF_ASM(vpalignr)
DEF_ASM(kmovb)
DEF_ASM(kmovw)
DEF_ASM(kmovd)
DEF_ASM(kmovq)
DEF_ASM(vprord)
DEF_ASM(vprorq)
DEF_ASM(vpblendmd)
DEF_ASM(vpblendmw)
DEF_ASM(andnl)
DEF_ASM(andnq)
DEF_ASM(shlxq)
DEF_ASM(sarxq)
DEF_ASM(shrxq)
DEF_ASM(rorxl)
DEF_ASM(rorxq)
DEF_ASM(vshufps)
DEF_ASM(vshufi32x4)
DEF_ASM(vshufi64x2)
DEF_ASM(valignq)
DEF_ASM(vblendpd)
DEF_ASM(vpblendd)
DEF_ASM(vblendvpd)
DEF_ASM(vpblendvb)
DEF_ASM(vpblendmb)
DEF_ASM(vpblendmq)
DEF_ASM(vmovdqa)
DEF_ASM(vmovdqu)
DEF_ASM(vmovdqa32)
DEF_ASM(vmovdqa64)
DEF_ASM(vmovdqu8)
DEF_ASM(vmovdqu32)
DEF_ASM(vmovdqu64)
DEF_ASM(vmovapd)
DEF_ASM(vmovupd)
DEF_ASM(vmovups)
DEF_ASM(vmovshdup)
DEF_ASM(vpmovzxdq)
DEF_ASM(vmovmskpd)
DEF_ASM(vmovd)
DEF_ASM(vmovq)
DEF_ASM(vpinsrd)
DEF_ASM(vpinsrq)
DEF_ASM(vpextrq)
DEF_ASM(vextracti128)
DEF_ASM(vextracti32x4)
DEF_ASM(vextracti64x2)
DEF_ASM(vextracti64x4)
DEF_ASM(vinserti128)
DEF_ASM(vinserti32x4)
DEF_ASM(vinserti64x2)
DEF_ASM(vinserti64x4)
DEF_ASM(vbroadcasti128)
DEF_ASM(vbroadcasti32x4)
DEF_ASM(vbroadcastf64x2)
DEF_ASM(vpbroadcastd)
DEF_ASM(vpbroadcastq)
DEF_ASM(vpshufd)
DEF_ASM(vpslld)
DEF_ASM(vpsrld)
DEF_ASM(vpsllq)
DEF_ASM(vpsrlq)
DEF_ASM(vpslldq)
DEF_ASM(vpsrldq)
DEF_ASM(vpsraq)
DEF_ASM(vprold)
DEF_ASM(vprolq)
DEF_ASM(vpsllvq)
DEF_ASM(vpsrlvq)
DEF_ASM(vzeroupper)
DEF_ASM(vzeroall)
