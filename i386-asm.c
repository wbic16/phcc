/*
 *  i386 specific functions for TCC assembler
 *
 *  Copyright (c) 2001, 2002 Fabrice Bellard
 *  Copyright (c) 2009 Frédéric Feret (x86_64 support)
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 */

#define USING_GLOBALS
#include "tcc.h"

#define MAX_OPERANDS 3

#define TOK_ASM_first TOK_ASM_clc
#define TOK_ASM_last TOK_ASM_emms
#define TOK_ASM_alllast TOK_ASM_subps

#define OPC_B          0x01  /* only used with OPC_WL */
#define OPC_WL         0x02  /* accepts w, l or no suffix */
#define OPC_BWL        (OPC_B | OPC_WL) /* accepts b, w, l or no suffix */
#define OPC_REG        0x04 /* register is added to opcode */
#define OPC_MODRM      0x08 /* modrm encoding */

#define OPCT_MASK      0x70
#define OPC_FWAIT      0x10 /* add fwait opcode */
#define OPC_SHIFT      0x20 /* shift opcodes */
#define OPC_ARITH      0x30 /* arithmetic opcodes */
#define OPC_FARITH     0x40 /* FPU arithmetic opcodes */
#define OPC_TEST       0x50 /* test opcodes */
#define OPC_0F01       0x60 /* 0x0f01XX (group 7, XX is 2nd opcode,
                               no operands and unstructured mod/rm) */
#define OPCT_IS(v,i) (((v) & OPCT_MASK) == (i))

#define OPC_0F        0x100 /* Is secondary map (0x0f prefix) */
#define OPC_48        0x200 /* Always has REX prefix */
#define OPC_0F38      0x400 /* Is 0x0f38 map: the stored opcode is an
                               optional prefix byte (0x66/0xf3, emitted
                               by the prefix switch) plus the final
                               opcode byte (F12) */
#ifdef TCC_TARGET_X86_64
# define OPC_WLQ     0x1000  /* accepts w, l, q or no suffix */
# define OPC_BWLQ    (OPC_B | OPC_WLQ) /* accepts b, w, l, q or no suffix */
# define OPC_WLX     OPC_WLQ
# define OPC_BWLX    OPC_BWLQ
#else
# define OPC_WLX     OPC_WL
# define OPC_BWLX    OPC_BWL
#endif

#define OPC_GROUP_SHIFT 13

/* in order to compress the operand type, we use specific operands and
   we or only with EA  */
enum {
    OPT_REG8=0, /* warning: value is hardcoded from TOK_ASM_xxx */
    OPT_REG16,  /* warning: value is hardcoded from TOK_ASM_xxx */
    OPT_REG32,  /* warning: value is hardcoded from TOK_ASM_xxx */
#ifdef TCC_TARGET_X86_64
    OPT_REG64,  /* warning: value is hardcoded from TOK_ASM_xxx */
#endif
    OPT_MMX,    /* warning: value is hardcoded from TOK_ASM_xxx */
    OPT_SSE,    /* warning: value is hardcoded from TOK_ASM_xxx */
    OPT_CR,     /* warning: value is hardcoded from TOK_ASM_xxx */
    OPT_TR,     /* warning: value is hardcoded from TOK_ASM_xxx */
    OPT_DB,     /* warning: value is hardcoded from TOK_ASM_xxx */
    OPT_SEG,
    OPT_ST,
#ifdef TCC_TARGET_X86_64
    OPT_REG8_LOW, /* %spl,%bpl,%sil,%dil, encoded like ah,ch,dh,bh, but
		     with REX prefix, not used in insn templates */
#endif
    OPT_IM8,
    OPT_IM8S,
    OPT_IM16,
    OPT_IM32,
#ifdef TCC_TARGET_X86_64
    OPT_IM64,
#endif
    OPT_EAX,    /* %al, %ax, %eax or %rax register */
    OPT_ST0,    /* %st(0) register */
    OPT_CL,     /* %cl register */
    OPT_DX,     /* %dx register */
    OPT_ADDR,   /* OP_EA with only offset */
    OPT_INDIR,  /* *(expr) */
    /* composite types */
    OPT_COMPOSITE_FIRST,
    OPT_IM,     /* IM8 | IM16 | IM32 */
    OPT_REG,    /* REG8 | REG16 | REG32 | REG64 */
    OPT_REGW,   /* REG16 | REG32 | REG64 */
    OPT_IMW,    /* IM16 | IM32 */
    OPT_MMXSSE, /* MMX | SSE */
    OPT_DISP,   /* Like OPT_ADDR, but emitted as displacement (for jumps) */
    OPT_DISP8,  /* Like OPT_ADDR, but only 8bit (short jumps) */
    /* can be ored with any OPT_xxx */
    OPT_EA = 0x80
};

#define OP_REG8   (1 << OPT_REG8)
#define OP_REG16  (1 << OPT_REG16)
#define OP_REG32  (1 << OPT_REG32)
#define OP_MMX    (1 << OPT_MMX)
#define OP_SSE    (1 << OPT_SSE)
#define OP_CR     (1 << OPT_CR)
#define OP_TR     (1 << OPT_TR)
#define OP_DB     (1 << OPT_DB)
#define OP_SEG    (1 << OPT_SEG)
#define OP_ST     (1 << OPT_ST)
#define OP_IM8    (1 << OPT_IM8)
#define OP_IM8S   (1 << OPT_IM8S)
#define OP_IM16   (1 << OPT_IM16)
#define OP_IM32   (1 << OPT_IM32)
#define OP_EAX    (1 << OPT_EAX)
#define OP_ST0    (1 << OPT_ST0)
#define OP_CL     (1 << OPT_CL)
#define OP_DX     (1 << OPT_DX)
#define OP_ADDR   (1 << OPT_ADDR)
#define OP_INDIR  (1 << OPT_INDIR)
#ifdef TCC_TARGET_X86_64
# define OP_REG64 (1 << OPT_REG64)
# define OP_REG8_LOW (1 << OPT_REG8_LOW)
# define OP_IM64  (1 << OPT_IM64)
# define OP_EA32  (OP_EA << 1)
#else
# define OP_REG64 0
# define OP_REG8_LOW 0
# define OP_IM64  0
# define OP_EA32  0
#endif

#define OP_EA     0x40000000u
#define OP_YMM    (1 << 23) /* %ymm0-%ymm31 (F31) */
#define OP_ZMM    (1 << 24) /* %zmm0-%zmm31 (F31) */
#define OP_KREG   (1 << 25) /* %k0-%k7 (F31) */
#define OP_VEC    (OP_SSE | OP_YMM | OP_ZMM)
#define OP_REG    (OP_REG8 | OP_REG16 | OP_REG32 | OP_REG64)

#ifdef TCC_TARGET_X86_64
# define TREG_XAX   TREG_RAX
# define TREG_XCX   TREG_RCX
# define TREG_XDX   TREG_RDX
# define TOK_ASM_xax TOK_ASM_rax
#else
# define TREG_XAX   TREG_EAX
# define TREG_XCX   TREG_ECX
# define TREG_XDX   TREG_EDX
# define TOK_ASM_xax TOK_ASM_eax
#endif

typedef struct ASMInstr {
    uint16_t sym;
    uint16_t opcode;
    uint16_t instr_type;
    uint8_t nb_ops;
    uint8_t op_type[MAX_OPERANDS]; /* see OP_xxx */
} ASMInstr;

typedef struct Operand {
    uint32_t type;
    int8_t  reg; /* register, -1 if none */
    int8_t  reg2; /* second register, -1 if none */
    uint8_t shift;
    ExprValue e;
} Operand;

static const uint8_t reg_to_size[9] = {
/*
    [OP_REG8] = 0,
    [OP_REG16] = 1,
    [OP_REG32] = 2,
#ifdef TCC_TARGET_X86_64
    [OP_REG64] = 3,
#endif
*/
    0, 0, 1, 0, 2, 0, 0, 0, 3
};

#define NB_TEST_OPCODES 30

static const uint8_t test_bits[NB_TEST_OPCODES] = {
 0x00, /* o */
 0x01, /* no */
 0x02, /* b */
 0x02, /* c */
 0x02, /* nae */
 0x03, /* nb */
 0x03, /* nc */
 0x03, /* ae */
 0x04, /* e */
 0x04, /* z */
 0x05, /* ne */
 0x05, /* nz */
 0x06, /* be */
 0x06, /* na */
 0x07, /* nbe */
 0x07, /* a */
 0x08, /* s */
 0x09, /* ns */
 0x0a, /* p */
 0x0a, /* pe */
 0x0b, /* np */
 0x0b, /* po */
 0x0c, /* l */
 0x0c, /* nge */
 0x0d, /* nl */
 0x0d, /* ge */
 0x0e, /* le */
 0x0e, /* ng */
 0x0f, /* nle */
 0x0f, /* g */
};

static const uint8_t segment_prefixes[] = {
 0x26, /* es */
 0x2e, /* cs */
 0x36, /* ss */
 0x3e, /* ds */
 0x64, /* fs */
 0x65  /* gs */
};

static const ASMInstr asm_instrs[] = {
#define ALT(x) x
/* This removes a 0x0f in the second byte */
#define O(o) ((uint64_t) ((((o) & 0xff00) == 0x0f00) ? ((((o) >> 8) & ~0xff) | ((o) & 0xff)) : (o)))
/* This constructs instr_type from opcode, type and group.  */
#define T(o,i,g) ((i) | ((g) << OPC_GROUP_SHIFT) | ((((o) & 0xff00) == 0x0f00) ? OPC_0F : 0))
#define DEF_ASM_OP0(name, opcode)
#define DEF_ASM_OP0L(name, opcode, group, instr_type) { TOK_ASM_ ## name, O(opcode), T(opcode, instr_type, group), 0, { 0 } },
#define DEF_ASM_OP1(name, opcode, group, instr_type, op0) { TOK_ASM_ ## name, O(opcode), T(opcode, instr_type, group), 1, { op0 }},
#define DEF_ASM_OP2(name, opcode, group, instr_type, op0, op1) { TOK_ASM_ ## name, O(opcode), T(opcode, instr_type, group), 2, { op0, op1 }},
#define DEF_ASM_OP3(name, opcode, group, instr_type, op0, op1, op2) { TOK_ASM_ ## name, O(opcode), T(opcode, instr_type, group), 3, { op0, op1, op2 }},
#ifdef TCC_TARGET_X86_64
# include "x86_64-asm.h"
#else
# include "i386-asm.h"
#endif
    /* last operation */
    { 0, },
};

static const uint16_t op0_codes[] = {
#define ALT(x)
#define DEF_ASM_OP0(x, opcode) opcode,
#define DEF_ASM_OP0L(name, opcode, group, instr_type)
#define DEF_ASM_OP1(name, opcode, group, instr_type, op0)
#define DEF_ASM_OP2(name, opcode, group, instr_type, op0, op1)
#define DEF_ASM_OP3(name, opcode, group, instr_type, op0, op1, op2)
#ifdef TCC_TARGET_X86_64
# include "x86_64-asm.h"
#else
# include "i386-asm.h"
#endif
};

static inline int get_reg_shift(TCCState *s1)
{
    int shift, v;
    v = asm_int_expr(s1);
    switch(v) {
    case 1:
        shift = 0;
        break;
    case 2:
        shift = 1;
        break;
    case 4:
        shift = 2;
        break;
    case 8:
        shift = 3;
        break;
    default:
        expect("1, 2, 4 or 8 constant");
        shift = 0;
        break;
    }
    return shift;
}

#ifdef TCC_TARGET_X86_64
static int asm_parse_numeric_reg(int t, unsigned int *type)
{
    int reg = -1;
    if (t >= TOK_IDENT && t < tok_ident) {
	const char *s = table_ident[t - TOK_IDENT]->str;
	char c;
	*type = OP_REG64;
	if (*s == 'c') {
	    s++;
	    *type = OP_CR;
	}
	if (*s++ != 'r')
	  return -1;
	/* Don't allow leading '0'.  */
	if ((c = *s++) >= '1' && c <= '9')
	  reg = c - '0';
	else
	  return -1;
	if ((c = *s) >= '0' && c <= '5')
	  s++, reg = reg * 10 + c - '0';
	if (reg > 15)
	  return -1;
	if ((c = *s) == 0)
	  ;
	else if (*type != OP_REG64)
	  return -1;
	else if (c == 'b' && !s[1])
	  *type = OP_REG8;
	else if (c == 'w' && !s[1])
	  *type = OP_REG16;
	else if (c == 'd' && !s[1])
	  *type = OP_REG32;
	else
	  return -1;
    }
    return reg;
}
#endif

static int asm_parse_reg(unsigned int *type)
{
    int reg = 0;
    *type = 0;
    if (tok != '%')
        goto error_32;
    next();
    if (tok >= TOK_ASM_eax && tok <= TOK_ASM_edi) {
        reg = tok - TOK_ASM_eax;
	*type = OP_REG32;
#ifdef TCC_TARGET_X86_64
    } else if (tok >= TOK_ASM_rax && tok <= TOK_ASM_rdi) {
        reg = tok - TOK_ASM_rax;
	*type = OP_REG64;
    } else if (tok == TOK_ASM_rip) {
        reg = -2; /* Probably should use different escape code. */
	*type = OP_REG64;
    } else if ((reg = asm_parse_numeric_reg(tok, type)) >= 0
	       && (*type == OP_REG32 || *type == OP_REG64)) {
	;
#endif
    } else {
    error_32:
        expect("register");
    }
    next();
    return reg;
}

static void parse_operand(TCCState *s1, Operand *op)
{
    ExprValue e;
    int reg, indir;
    const char *p;

    indir = 0;
    if (tok == '*') {
        next();
        indir = OP_INDIR;
    }

    if (tok == '%') {
        next();
        if (tok >= TOK_ASM_al && tok <= TOK_ASM_db7) {
            reg = tok - TOK_ASM_al;
            op->type = 1 << (reg >> 3); /* WARNING: do not change constant order */
            op->reg = reg & 7;
            if ((op->type & OP_REG) && op->reg == TREG_XAX)
                op->type |= OP_EAX;
            else if (op->type == OP_REG8 && op->reg == TREG_XCX)
                op->type |= OP_CL;
            else if (op->type == OP_REG16 && op->reg == TREG_XDX)
                op->type |= OP_DX;
        } else if (tok >= TOK_ASM_dr0 && tok <= TOK_ASM_dr7) {
            op->type = OP_DB;
            op->reg = tok - TOK_ASM_dr0;
        } else if (tok >= TOK_ASM_es && tok <= TOK_ASM_gs) {
            op->type = OP_SEG;
            op->reg = tok - TOK_ASM_es;
        } else if (tok == TOK_ASM_st) {
            op->type = OP_ST;
            op->reg = 0;
            next();
            if (tok == '(') {
                next();
                if (tok != TOK_PPNUM)
                    goto reg_error;
                p = tokc.str.data;
                reg = p[0] - '0';
                if ((unsigned)reg >= 8 || p[1] != '\0')
                    goto reg_error;
                op->reg = reg;
                next();
                skip(')');
            }
            if (op->reg == 0)
                op->type |= OP_ST0;
            goto no_skip;
#ifdef TCC_TARGET_X86_64
	} else if (tok >= TOK_ASM_spl && tok <= TOK_ASM_dil) {
	    op->type = OP_REG8 | OP_REG8_LOW;
	    op->reg = 4 + tok - TOK_ASM_spl;
	} else if (tok >= TOK_ASM_xmm8 && tok <= TOK_ASM_xmm15) {
	    /* high SSE registers: the encoder's REX logic handles
	       register numbers 8..15 for OP_SSE operands */
	    op->type = OP_SSE;
	    op->reg = 8 + tok - TOK_ASM_xmm8;
	} else if (tok >= TOK_ASM_xmm16 && tok <= TOK_ASM_xmm31) {
	    /* EVEX-only registers: recognised here so the VEX path can
	       encode them; legacy instructions reject them in operand
	       matching (their numbers fall outside every legacy form) */
	    op->type = OP_SSE;
	    op->reg = 16 + tok - TOK_ASM_xmm16;
	} else if (tok >= TOK_ASM_ymm0 && tok <= TOK_ASM_ymm31) {
	    op->type = OP_YMM;
	    op->reg = tok - TOK_ASM_ymm0;
	} else if (tok >= TOK_ASM_zmm0 && tok <= TOK_ASM_zmm31) {
	    op->type = OP_ZMM;
	    op->reg = tok - TOK_ASM_zmm0;
	} else if (tok >= TOK_ASM_k0 && tok <= TOK_ASM_k7) {
	    op->type = OP_KREG;
	    op->reg = tok - TOK_ASM_k0;
        } else if ((op->reg = asm_parse_numeric_reg(tok, &op->type)) >= 0) {
	    ;
#endif
        } else {
        reg_error:
            tcc_error("unknown register %%%s", get_tok_str(tok, &tokc));
        }
        next();
    no_skip: ;
    } else if (tok == '$') {
        /* constant value */
        next();
        asm_expr(s1, &e);
        op->type = OP_IM32;
        op->e = e;
        if (!op->e.sym) {
            if (op->e.v == (uint8_t)op->e.v)
                op->type |= OP_IM8;
            if (op->e.v == (int8_t)op->e.v)
                op->type |= OP_IM8S;
            if (op->e.v == (uint16_t)op->e.v)
                op->type |= OP_IM16;
#ifdef TCC_TARGET_X86_64
            if (op->e.v != (int32_t)op->e.v && op->e.v != (uint32_t)op->e.v)
                op->type = OP_IM64;
#endif
        }
    } else {
        /* address(reg,reg2,shift) with all variants */
        op->type = OP_EA;
        op->reg = -1;
        op->reg2 = -1;
        op->shift = 0;
        if (tok != '(') {
            asm_expr(s1, &e);
            op->e = e;
        } else {
            next();
            if (tok == '%' || tok == ',') {
                /* (%reg...) register indirect, or (,index,scale)
                   base-less SIB: no displacement expression; the
                   '(' block below parses the register fields */
                unget_tok('(');
                op->e.v = 0;
                op->e.sym = NULL;
            } else {
                /* bracketed offset expression */
                asm_expr(s1, &e);
                if (tok != ')')
                    expect(")");
                next();
                op->e.v = e.v;
                op->e.sym = e.sym;
            }
	    op->e.pcrel = 0;
        }
        if (tok == '(') {
	    unsigned int type = 0;
            next();
            if (tok != ',') {
                op->reg = asm_parse_reg(&type);
            }
            if (tok == ',') {
                next();
                if (tok != ',') {
                    op->reg2 = asm_parse_reg(&type);
                }
                if (tok == ',') {
                    next();
                    op->shift = get_reg_shift(s1);
                }
            }
	    if (type & OP_REG32)
	        op->type |= OP_EA32;
            skip(')');
        }
        if (op->reg == -1 && op->reg2 == -1)
            op->type |= OP_ADDR;
    }
    op->type |= indir;
}

/* XXX: unify with C code output ? */
ST_FUNC void gen_expr32(ExprValue *pe)
{
    if (!pe->pcrel && pe->sym && asm_label_diff_emit(pe->sym, pe->v, 4)) {
        /* deferred label difference: zero field, patched later */
        gen_le32(0);
        return;
    }
    if (pe->pcrel)
        /* If PC-relative, always set VT_SYM, even without symbol,
	   so as to force a relocation to be emitted.  */
	gen_addrpc32(VT_SYM, pe->sym, pe->v + (ind + 4));
    else
	gen_addr32(pe->sym ? VT_SYM : 0, pe->sym, pe->v);
}

/* Sub-word variants of gen_expr32 for the data directives that take
   symbol operands at width 2 and 1 (.word/.short/.value/.hword/.2byte
   and .byte): the same three cases — deferred label difference,
   PC-relative, plain — with the addend conventions of
   gen_addr32/gen_addrpc32 (on RELA targets the value travels in the
   addend and the field carries the pc-relative residue or zero; on
   REL targets it stays in the field). */
ST_FUNC void gen_expr16(ExprValue *pe)
{
    if (!pe->pcrel && pe->sym && asm_label_diff_emit(pe->sym, pe->v, 2)) {
        /* deferred label difference: zero field, patched later */
        gen_le16(0);
        return;
    }
    if (pe->pcrel) {
        int c = pe->v + (ind + 2);
#ifdef TCC_TARGET_X86_64
        greloca(cur_text_section, pe->sym, ind, R_X86_64_PC16, c - 2);
#else
        greloc(cur_text_section, pe->sym, ind, R_386_PC16);
#endif
        gen_le16(c - 2);
    } else if (pe->sym) {
#ifdef TCC_TARGET_X86_64
        greloca(cur_text_section, pe->sym, ind, R_X86_64_16, pe->v);
        gen_le16(0);
#else
        greloc(cur_text_section, pe->sym, ind, R_386_16);
        gen_le16(pe->v);
#endif
    } else
        gen_le16(pe->v);
}

ST_FUNC void gen_expr8(ExprValue *pe)
{
    if (!pe->pcrel && pe->sym && asm_label_diff_emit(pe->sym, pe->v, 1)) {
        /* deferred label difference: zero field, patched later */
        g(0);
        return;
    }
    if (pe->pcrel) {
        int c = pe->v + (ind + 1);
#ifdef TCC_TARGET_X86_64
        greloca(cur_text_section, pe->sym, ind, R_X86_64_PC8, c - 1);
#else
        greloc(cur_text_section, pe->sym, ind, R_386_PC8);
#endif
        g(c - 1);
    } else if (pe->sym) {
#ifdef TCC_TARGET_X86_64
        greloca(cur_text_section, pe->sym, ind, R_X86_64_8, pe->v);
        g(0);
#else
        greloc(cur_text_section, pe->sym, ind, R_386_8);
        g(pe->v);
#endif
    } else
        g(pe->v);
}

/* XXX: unify with C code output ? */
static void gen_disp32(ExprValue *pe)
{
    Sym *sym = pe->sym;
    ElfSym *esym = elfsym(sym);
    if (sym && asm_label_diff_is(sym))
        tcc_error("label difference cannot be used as a jump displacement");
    if (esym && esym->st_shndx == cur_text_section->sh_num) {
        /* same section: we can output an absolute value. Note
           that the TCC compiler behaves differently here because
           it always outputs a relocation to ease (future) code
           elimination in the linker */
        gen_le32(pe->v + esym->st_value - ind - 4);
    } else {
        if (sym && sym->type.t == VT_VOID) {
            sym->type.t = VT_FUNC;
            sym->type.ref = NULL;
        }
#ifdef TCC_TARGET_X86_64
        greloca(cur_text_section, sym, ind, R_X86_64_PLT32, pe->v - 4);
        gen_le32(0);
#else
        gen_addrpc32(VT_SYM, sym, pe->v);
#endif

    }
}

/* generate the modrm operand */
static inline int asm_modrm(int reg, Operand *op)
{
    int mod, reg1, reg2, sib_reg1;

    if (op->type & (OP_REG | OP_MMX | OP_SSE)) {
        g(0xc0 + (reg << 3) + op->reg);
    } else if (op->reg == -1 && op->reg2 == -1) {
        /* displacement only */
#ifdef TCC_TARGET_X86_64
	g(0x04 + (reg << 3));
	g(0x25);
#else
	g(0x05 + (reg << 3));
#endif
	gen_expr32(&op->e);
#ifdef TCC_TARGET_X86_64
    } else if (op->reg == -2) {
        ExprValue *pe = &op->e;
        g(0x05 + (reg << 3));
        gen_addrpc32(pe->sym ? VT_SYM : 0, pe->sym, pe->v);
        return ind;
#endif
    } else {
        sib_reg1 = op->reg;
        /* fist compute displacement encoding */
        if (sib_reg1 == -1) {
            sib_reg1 = 5;
            mod = 0x00;
        } else if (op->e.v == 0 && !op->e.sym && op->reg != 5) {
            mod = 0x00;
        } else if (op->e.v == (int8_t)op->e.v && !op->e.sym) {
            mod = 0x40;
        } else {
            mod = 0x80;
        }
        /* compute if sib byte needed */
        reg1 = op->reg;
        if (op->reg2 != -1)
            reg1 = 4;
        g(mod + (reg << 3) + reg1);
        if (reg1 == 4) {
            /* add sib byte */
            reg2 = op->reg2;
            if (reg2 == -1)
                reg2 = 4; /* indicate no index */
            g((op->shift << 6) + (reg2 << 3) + sib_reg1);
        }
        /* add offset */
        if (mod == 0x40) {
            g(op->e.v);
        } else if (mod == 0x80 || op->reg == -1) {
	    gen_expr32(&op->e);
        }
    }
    return 0;
}

#ifdef TCC_TARGET_X86_64
#define REX_W 0x48
#define REX_R 0x44
#define REX_X 0x42
#define REX_B 0x41

static void asm_rex(int width64, Operand *ops, int nb_ops, int *op_type,
		    int regi, int rmi)
{
  unsigned char rex = width64 ? 0x48 : 0;
  int saw_high_8bit = 0;
  int i;
  if (rmi == -1) {
      /* No mod/rm byte, but we might have a register op nevertheless
         (we will add it to the opcode later).  */
      for(i = 0; i < nb_ops; i++) {
	  if (op_type[i] & (OP_REG | OP_ST)) {
	      if (ops[i].reg >= 8) {
		  rex |= REX_B;
		  ops[i].reg -= 8;
	      } else if (ops[i].type & OP_REG8_LOW)
		  rex |= 0x40;
	      else if (ops[i].type & OP_REG8 && ops[i].reg >= 4)
		  /* An 8 bit reg >= 4 without REG8 is ah/ch/dh/bh */
		  saw_high_8bit = ops[i].reg;
	      break;
	  }
      }
  } else {
      if (regi != -1) {
	  if (ops[regi].reg >= 8) {
	      rex |= REX_R;
	      ops[regi].reg -= 8;
	  } else if (ops[regi].type & OP_REG8_LOW)
	      rex |= 0x40;
	  else if (ops[regi].type & OP_REG8 && ops[regi].reg >= 4)
	      /* An 8 bit reg >= 4 without REG8 is ah/ch/dh/bh */
	      saw_high_8bit = ops[regi].reg;
      }
      if (ops[rmi].type & (OP_REG | OP_MMX | OP_SSE | OP_CR | OP_EA)) {
	  if (ops[rmi].reg >= 8) {
	      rex |= REX_B;
	      ops[rmi].reg -= 8;
	  } else if (ops[rmi].type & OP_REG8_LOW)
	      rex |= 0x40;
	  else if (ops[rmi].type & OP_REG8 && ops[rmi].reg >= 4)
	      /* An 8 bit reg >= 4 without REG8 is ah/ch/dh/bh */
	      saw_high_8bit = ops[rmi].reg;
      }
      if (ops[rmi].type & OP_EA && ops[rmi].reg2 >= 8) {
	  rex |= REX_X;
	  ops[rmi].reg2 -= 8;
      }
  }
  if (rex) {
      if (saw_high_8bit)
	  tcc_error("can't encode register %%%ch when REX prefix is required",
		    "acdb"[saw_high_8bit-4]);
      g(rex);
  }
}
#endif


static void maybe_print_stats (void)
{
    static int already;

    if (0 && !already)
    /* print stats about opcodes */
    {
        const struct ASMInstr *pa;
        int freq[4];
        int op_vals[500];
        int nb_op_vals, i, j;

	already = 1;
        nb_op_vals = 0;
        memset(freq, 0, sizeof(freq));
        for(pa = asm_instrs; pa->sym != 0; pa++) {
            freq[pa->nb_ops]++;
            //for(i=0;i<pa->nb_ops;i++) {
                for(j=0;j<nb_op_vals;j++) {
                    //if (pa->op_type[i] == op_vals[j])
                    if (pa->instr_type == op_vals[j])
                        goto found;
                }
                //op_vals[nb_op_vals++] = pa->op_type[i];
                op_vals[nb_op_vals++] = pa->instr_type;
            found: ;
            //}
        }
        for(i=0;i<nb_op_vals;i++) {
            int v = op_vals[i];
            //if ((v & (v - 1)) != 0)
                printf("%3d: %08x\n", i, v);
        }
        printf("size=%d nb=%d f0=%d f1=%d f2=%d f3=%d\n",
               (int)sizeof(asm_instrs),
	       (int)sizeof(asm_instrs) / (int)sizeof(ASMInstr),
               freq[0], freq[1], freq[2], freq[3]);
    }
}


#ifdef TCC_TARGET_X86_64

/* ------------------------------------------------------------------ */
/* F31: VEX/EVEX assembler support — the prefix frontier recorded in
   F12.  The measured surface is the OpenSSL 4.1.0 perlasm corpus
   (42 files, 100 mnemonics, ~130k instruction lines): 2-byte VEX
   (C5), 3-byte VEX (C4), EVEX (62) with writemask {%k} and zeroing
   {z} decorations, L'L vector lengths 128/256/512, and BMI2 mulx
   (which falls out as a general-purpose-register NDS3 form).
   Anything outside the table fails with the assembler's existing
   loud errors, never a silent mis-assembly.

   The encoder is an explicit prefix-decoding state machine:

     VSM_OPERANDS  parse operands and {%k}/{z} decorations
     VSM_CLASSIFY  resolve operand roles per form; choose the prefix
                   family (C5 when it can express the instruction,
                   else C4, else EVEX when the operands or the form
                   demand it: EVEX-only mnemonic, zmm width, any
                   vector register >= 16, or a writemask decoration)
     VSM_PREFIX    emit 0x67 if an operand asked for it, then the
                   C5/C4/62 prefix with all extension bits inverted
                   in place (R/X/B/R'/V')
     VSM_OPCODE    emit the opcode byte (the map rides in the
                   prefix; there is no separate map escape byte)
     VSM_MODRM     emit ModRM/SIB/displacement via asm_modrm_vex,
                   which adds EVEX's compressed disp8*N addressing
                   on top of the legacy displacement logic
     VSM_IMM       emit the trailing imm8 (or the is4 byte)
     VSM_DONE

   AT&T operand order is source-first, so for the three-operand
   forms the roles are [rm, vvvv, reg]: the last-written operand is
   the destination and lands in ModRM.reg.  mulx is the same role
   pattern over general-purpose registers. */

enum { MW_FULL, MW_4, MW_8, MW_16, MW_32 }; /* EVEX disp8*N widths */

enum {
    VF_NDS3,    /* [rm, vvvv, reg]                            */
    VF_NDS3I,   /* [$imm, rm, vvvv, reg] + imm8               */
    VF_IS4,     /* AT&T [ctrl, src1, src2, dst] = [is4, rm, vvvv, reg] */
    VF_MOV2,    /* [a, b]: load or store by operand classes   */
    VF_EXTRACT, /* [$imm, reg, rm] + imm8                     */
    VF_SHIFTI,  /* [$imm, rm, dst-in-vvvv] + imm8, /ext       */
    VF_PERMI,   /* [$imm, rm, reg] + imm8                     */
    VF_MOVMSK,  /* [vec rm, gpr reg]                          */
    VF_MOVDQ,   /* [gpr/mem, vec] or [vec, gpr/mem]           */
    VF_MOVQ,    /* vmovq: four GAS forms by operand classes   */
    VF_BCAST,   /* [src, reg]                                 */
    VF_KCMP,    /* [$imm, rm, vvvv, kreg] + imm8              */
    VF_KMOV,    /* [a, b]: one side is a k register; opcode
                   holds the memory-load byte (0x90), opcode2
                   the memory-store byte, pp the memory pp and
                   ext the GPR pp; GPR forms add 2 to the byte  */
    VF_ZERO     /* no operands (ext holds the VEX L bit)      */
};

#define VX_EVEONLY 0x01 /* EVEX encoding exists only */
#define VX_W0VEX   0x02 /* entry w is the EVEX W; a VEX prefix writes 0 */
#define VX_RMGPR   0x04 /* rm slot may be a general-purpose register */
#define VX_SRCGPR  0x08 /* broadcast source may be a GPR */
#define VX_GPR     0x10 /* NDS3 roles are GPRs, not vectors (mulx) */
#define VX_WGPR    0x20 /* W comes from the reg operand's width (mulx) */
#define VX_MIXEDW  0x40 /* vector operand widths may differ (vpmovzxdq) */
#define VX_SWAPVV  0x80 /* NDS3: vvvv is operand 0, rm operand 1
                           (the BMI2 shifts, unlike mulx) */
#define VX_EVEXPREF 0x200 /* EVEX by default, but a VEX encoding
                           exists and {vex} selects it (vpmadd52) */

#define PP_66 1
#define PP_F3 2
#define PP_F2 3

typedef struct VEXInstr {
    uint16_t sym;
    uint8_t map;     /* 1 = 0F, 2 = 0F38, 3 = 0F3A */
    uint8_t opcode;  /* main (load-direction) opcode byte */
    uint8_t opcode2; /* store-direction opcode for MOV2/MOVDQ, else 0 */
    uint8_t pp;      /* raw pp bits: 0 none, 1 = 66, 2 = F3, 3 = F2 */
    uint8_t w;
    uint8_t form;
    uint8_t ext;     /* VF_SHIFTI: ModRM.reg extension; VF_ZERO: L bit;
                        VF_KMOV: the GPR-form pp */
    uint16_t flags;
    uint8_t mw;      /* EVEX memory width class for disp8*N */
} VEXInstr;

#define VEXI(name, map, op, op2, pp, w, form, ext, flags, mw) \
    { TOK_ASM_ ## name, map, op, op2, pp, w, form, ext, flags, mw }

static const VEXInstr vex_instrs[] = {
    /* BMI2: NDS3 over GPRs; W is the operand width */
    VEXI(mulx,  2, 0xf6, 0, PP_F2, 0, VF_NDS3, 0, VX_GPR | VX_WGPR, MW_FULL),
    VEXI(mulxl, 2, 0xf6, 0, PP_F2, 0, VF_NDS3, 0, VX_GPR, MW_FULL),
    VEXI(mulxq, 2, 0xf6, 0, PP_F2, 1, VF_NDS3, 0, VX_GPR, MW_FULL),
    /* AES */
    VEXI(vaesenc,     2, 0xdc, 0, PP_66, 0, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vaesenclast, 2, 0xdd, 0, PP_66, 0, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vaesdec,     2, 0xde, 0, PP_66, 0, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vaesdeclast, 2, 0xdf, 0, PP_66, 0, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vpclmulqdq,  3, 0x44, 0, PP_66, 0, VF_NDS3I, 0, 0, MW_FULL),
    /* integer ALU */
    VEXI(vpaddb, 1, 0xfc, 0, PP_66, 0, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vpaddd, 1, 0xfe, 0, PP_66, 0, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vpaddq, 1, 0xd4, 0, PP_66, 1, VF_NDS3, 0, VX_W0VEX, MW_FULL),
    VEXI(vpsubd, 1, 0xfa, 0, PP_66, 0, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vpsubq, 1, 0xfb, 0, PP_66, 1, VF_NDS3, 0, VX_W0VEX, MW_FULL),
    VEXI(vpand,  1, 0xdb, 0, PP_66, 0, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vpandn, 1, 0xdf, 0, PP_66, 0, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vpandd, 1, 0xdb, 0, PP_66, 0, VF_NDS3, 0, VX_EVEONLY, MW_FULL),
    VEXI(vpandq, 1, 0xdb, 0, PP_66, 1, VF_NDS3, 0, VX_EVEONLY, MW_FULL),
    VEXI(vpor,   1, 0xeb, 0, PP_66, 0, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vporq,  1, 0xeb, 0, PP_66, 1, VF_NDS3, 0, VX_EVEONLY, MW_FULL),
    VEXI(vpxor,  1, 0xef, 0, PP_66, 0, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vpxord, 1, 0xef, 0, PP_66, 0, VF_NDS3, 0, VX_EVEONLY, MW_FULL),
    VEXI(vpxorq, 1, 0xef, 0, PP_66, 1, VF_NDS3, 0, VX_EVEONLY, MW_FULL),
    VEXI(vxorps, 1, 0x57, 0, 0,     0, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vpshufb, 2, 0x00, 0, PP_66, 0, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vpunpckldq,  1, 0x62, 0, PP_66, 0, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vpunpckhdq,  1, 0x6a, 0, PP_66, 0, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vpunpcklqdq, 1, 0x6c, 0, PP_66, 1, VF_NDS3, 0, VX_W0VEX, MW_FULL),
    VEXI(vpunpckhqdq, 1, 0x6d, 0, PP_66, 1, VF_NDS3, 0, VX_W0VEX, MW_FULL),
    VEXI(vpmuludq, 1, 0xf4, 0, PP_66, 1, VF_NDS3, 0, VX_W0VEX, MW_FULL),
    VEXI(vpsllvq, 2, 0x47, 0, PP_66, 1, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vpsrlvq, 2, 0x45, 0, PP_66, 1, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vpermd,  2, 0x36, 0, PP_66, 0, VF_NDS3, 0, 0, MW_FULL),
    /* compares: legacy vector-dst forms, then EVEX mask-dst forms */
    VEXI(vpcmpeqd, 1, 0x76, 0, PP_66, 0, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vpcmpgtd, 1, 0x66, 0, PP_66, 0, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vpcmpeqq, 2, 0x29, 0, PP_66, 1, VF_NDS3, 0, VX_W0VEX, MW_FULL),
    VEXI(vpcmpgtq, 2, 0x37, 0, PP_66, 1, VF_NDS3, 0, VX_W0VEX, MW_FULL),
    /* BMI2 andn: plain NDS3 over GPRs, no pp (measured) */
    VEXI(andnl, 2, 0xf2, 0, 0, 0, VF_NDS3, 0, VX_GPR, MW_FULL),
    VEXI(andnq, 2, 0xf2, 0, 0, 1, VF_NDS3, 0, VX_GPR, MW_FULL),
    /* BMI2 shifts: the mulx role pattern over GPRs (count in
       vvvv, source in rm, destination in ModRM.reg); the pp
       values are GAS's bytes (shlx 01, sarx 10, shrx 11) */
    VEXI(shlxq, 2, 0xf7, 0, PP_66, 1, VF_NDS3, 0, VX_GPR | VX_SWAPVV, MW_FULL),
    VEXI(sarxq, 2, 0xf7, 0, PP_F3, 1, VF_NDS3, 0, VX_GPR | VX_SWAPVV, MW_FULL),
    VEXI(shrxq, 2, 0xf7, 0, PP_F2, 1, VF_NDS3, 0, VX_GPR | VX_SWAPVV, MW_FULL),
    /* opmask moves, VEX-encoded (measured from GAS bytes):
       memory forms 0x90/0x91 with k in ModRM.reg; GPR forms
       0x92/0x93, where a GPR store puts the k register in rm */
    /* for VF_KMOV, w is the memory-form W and ext packs the
       GPR form as (W << 7) | pp: kmovd's memory form is W1 but
       its GPR form is W0, which is why GAS gives the GPR form a
       2-byte VEX and the memory form a 3-byte one */
    VEXI(kmovw, 1, 0x90, 0x91, 0,     0, VF_KMOV, 0,          0, MW_FULL),
    VEXI(kmovb, 1, 0x90, 0x91, PP_66, 0, VF_KMOV, PP_66,      0, MW_FULL),
    VEXI(kmovd, 1, 0x90, 0x91, PP_66, 1, VF_KMOV, PP_F2,      0, MW_FULL),
    VEXI(kmovq, 1, 0x90, 0x91, 0,     1, VF_KMOV, PP_F2 | 0x80, 0, MW_FULL),
    VEXI(vpcmpq,   3, 0x1f, 0, PP_66, 1, VF_KCMP, 0, VX_EVEONLY, MW_FULL),
    VEXI(vpcmpuq,  3, 0x1e, 0, PP_66, 1, VF_KCMP, 0, VX_EVEONLY, MW_FULL),
    /* imm8 forms */
    VEXI(vpternlogq, 3, 0x25, 0, PP_66, 1, VF_NDS3I, 0, VX_EVEONLY, MW_FULL),
    VEXI(vperm2i128, 3, 0x46, 0, PP_66, 0, VF_NDS3I, 0, 0, MW_FULL),
    VEXI(vshufps,    1, 0xc6, 0, 0,     0, VF_NDS3I, 0, 0, MW_FULL),
    VEXI(vshufi32x4, 3, 0x43, 0, PP_66, 0, VF_NDS3I, 0, VX_EVEONLY, MW_FULL),
    VEXI(vshufi64x2, 3, 0x43, 0, PP_66, 1, VF_NDS3I, 0, VX_EVEONLY, MW_FULL),
    VEXI(valignq,    3, 0x03, 0, PP_66, 1, VF_NDS3I, 0, VX_EVEONLY, MW_FULL),
    VEXI(vblendpd,   3, 0x0d, 0, PP_66, 0, VF_NDS3I, 0, 0, MW_FULL),
    VEXI(vpblendd,   3, 0x02, 0, PP_66, 0, VF_NDS3I, 0, 0, MW_FULL),
    VEXI(vpalignr,   3, 0x0f, 0, PP_66, 0, VF_NDS3I, 0, 0, MW_FULL),
    /* BMI2 rotate: an imm8 GPR form on the PERMI skeleton */
    VEXI(rorxl,      3, 0xf0, 0, PP_F2, 0, VF_PERMI, 0, VX_GPR, MW_FULL),
    VEXI(rorxq,      3, 0xf0, 0, PP_F2, 1, VF_PERMI, 0, VX_GPR, MW_FULL),
    /* AVX512-IFMA: EVEX by default (even at 256 bit), {vex}
       selects the VEX encoding GAS also carries */
    VEXI(vpmadd52luq, 2, 0xb4, 0, PP_66, 1, VF_NDS3, 0, VX_EVEXPREF, MW_FULL),
    VEXI(vpmadd52huq, 2, 0xb5, 0, PP_66, 1, VF_NDS3, 0, VX_EVEXPREF, MW_FULL),
    VEXI(vblendvpd,  3, 0x4b, 0, PP_66, 0, VF_IS4, 0, 0, MW_FULL),
    VEXI(vpblendvb,  3, 0x4c, 0, PP_66, 0, VF_IS4, 0, 0, MW_FULL),
    VEXI(vpblendmb,  2, 0x66, 0, PP_66, 0, VF_NDS3, 0, VX_EVEONLY, MW_FULL),
    VEXI(vpblendmw,  2, 0x66, 0, PP_66, 1, VF_NDS3, 0, VX_EVEONLY, MW_FULL),
    VEXI(vpblendmd,  2, 0x64, 0, PP_66, 0, VF_NDS3, 0, VX_EVEONLY, MW_FULL),
    VEXI(vpblendmq,  2, 0x64, 0, PP_66, 1, VF_NDS3, 0, VX_EVEONLY, MW_FULL),
    VEXI(vpermq,     3, 0x00, 0, PP_66, 1, VF_PERMI, 0, 0, MW_FULL),
    VEXI(vpermpd,    3, 0x01, 0, PP_66, 1, VF_PERMI, 0, 0, MW_FULL),
    VEXI(vpermilps,  3, 0x04, 0, PP_66, 0, VF_PERMI, 0, 0, MW_FULL),
    VEXI(vpermilpd,  3, 0x05, 0, PP_66, 1, VF_PERMI, 0, 0, MW_FULL),
    /* register forms of the permutes: dual-form mnemonics, the
       entry is chosen by whether operand 0 is an immediate */
    VEXI(vpermq,     2, 0x36, 0, PP_66, 1, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vpermpd,    2, 0x36, 0, PP_F3, 1, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vpermilps,  2, 0x0C, 0, 0,     0, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vpermilpd,  2, 0x0D, 0, PP_66, 0, VF_NDS3, 0, 0, MW_FULL),
    VEXI(vpshufd,    1, 0x70, 0, PP_66, 0, VF_PERMI, 0, 0, MW_FULL),
    /* shifts by imm8: destination rides in VEX.vvvv, /ext in ModRM.reg */
    VEXI(vpslld,  1, 0x72, 0, PP_66, 0, VF_SHIFTI, 6, 0, MW_FULL),
    VEXI(vpsrld,  1, 0x72, 0, PP_66, 0, VF_SHIFTI, 2, 0, MW_FULL),
    VEXI(vpsllq,  1, 0x73, 0, PP_66, 1, VF_SHIFTI, 6, VX_W0VEX, MW_FULL),
    VEXI(vpsrlq,  1, 0x73, 0, PP_66, 1, VF_SHIFTI, 2, VX_W0VEX, MW_FULL),
    VEXI(vpslldq, 1, 0x73, 0, PP_66, 0, VF_SHIFTI, 7, 0, MW_FULL),
    VEXI(vpsrldq, 1, 0x73, 0, PP_66, 0, VF_SHIFTI, 3, 0, MW_FULL),
    VEXI(vpsraq,  1, 0x72, 0, PP_66, 1, VF_SHIFTI, 4, VX_EVEONLY, MW_FULL),
    VEXI(vprold,  1, 0x72, 0, PP_66, 0, VF_SHIFTI, 1, VX_EVEONLY, MW_FULL),
    VEXI(vprolq,  1, 0x72, 0, PP_66, 1, VF_SHIFTI, 1, VX_EVEONLY, MW_FULL),
    VEXI(vprord,  1, 0x72, 0, PP_66, 0, VF_SHIFTI, 0, VX_EVEONLY, MW_FULL),
    VEXI(vprorq,  1, 0x72, 0, PP_66, 1, VF_SHIFTI, 0, VX_EVEONLY, MW_FULL),
    /* moves */
    VEXI(vmovdqa,   1, 0x6f, 0x7f, PP_66, 0, VF_MOV2, 0, 0, MW_FULL),
    VEXI(vmovdqu,   1, 0x6f, 0x7f, PP_F3, 0, VF_MOV2, 0, 0, MW_FULL),
    VEXI(vmovdqa32, 1, 0x6f, 0x7f, PP_66, 0, VF_MOV2, 0, VX_EVEONLY, MW_FULL),
    VEXI(vmovdqa64, 1, 0x6f, 0x7f, PP_66, 1, VF_MOV2, 0, VX_EVEONLY, MW_FULL),
    VEXI(vmovdqu8,  1, 0x6f, 0x7f, PP_F2, 0, VF_MOV2, 0, VX_EVEONLY, MW_FULL),
    VEXI(vmovdqu32, 1, 0x6f, 0x7f, PP_F3, 0, VF_MOV2, 0, VX_EVEONLY, MW_FULL),
    VEXI(vmovdqu64, 1, 0x6f, 0x7f, PP_F3, 1, VF_MOV2, 0, VX_EVEONLY, MW_FULL),
    VEXI(vmovapd,   1, 0x28, 0x29, PP_66, 0, VF_MOV2, 0, 0, MW_FULL),
    VEXI(vmovupd,   1, 0x10, 0x11, PP_66, 0, VF_MOV2, 0, 0, MW_FULL),
    VEXI(vmovups,   1, 0x10, 0x11, 0,     0, VF_MOV2, 0, 0, MW_FULL),
    VEXI(vmovshdup, 1, 0x16, 0,    PP_F3, 0, VF_MOV2, 0, 0, MW_FULL),
    VEXI(vpmovzxdq, 2, 0x35, 0,    PP_66, 0, VF_MOV2, 0, VX_MIXEDW, MW_8),
    VEXI(vmovmskpd, 1, 0x50, 0,    PP_66, 0, VF_MOVMSK, 0, 0, MW_FULL),
    VEXI(vmovd,     1, 0x6e, 0x7e, PP_66, 0, VF_MOVDQ, PP_66, 0, MW_4),
    VEXI(vmovq,     1, 0x6e, 0x7e, PP_66, 1, VF_MOVQ, 0xd6, 0, MW_8),
    /* insert / extract */
    VEXI(vpinsrd, 3, 0x22, 0, PP_66, 0, VF_NDS3I, 0, VX_RMGPR, MW_4),
    VEXI(vpinsrq, 3, 0x22, 0, PP_66, 1, VF_NDS3I, 0, VX_RMGPR, MW_8),
    VEXI(vpextrq, 3, 0x16, 0, PP_66, 1, VF_EXTRACT, 0, VX_RMGPR, MW_8),
    VEXI(vextracti128, 3, 0x39, 0, PP_66, 0, VF_EXTRACT, 0, 0, MW_16),
    VEXI(vextracti32x4, 3, 0x39, 0, PP_66, 0, VF_EXTRACT, 1, VX_EVEONLY, MW_16),
    VEXI(vextracti64x2, 3, 0x39, 0, PP_66, 1, VF_EXTRACT, 0, VX_EVEONLY, MW_16),
    VEXI(vextracti64x4, 3, 0x3b, 0, PP_66, 1, VF_EXTRACT, 1, VX_EVEONLY, MW_32),
    VEXI(vinserti128, 3, 0x38, 0, PP_66, 0, VF_NDS3I, 0, 0, MW_16),
    VEXI(vinserti32x4, 3, 0x38, 0, PP_66, 0, VF_NDS3I, 0, VX_EVEONLY, MW_16),
    VEXI(vinserti64x2, 3, 0x38, 0, PP_66, 1, VF_NDS3I, 0, VX_EVEONLY, MW_16),
    VEXI(vinserti64x4, 3, 0x3a, 0, PP_66, 1, VF_NDS3I, 0, VX_EVEONLY, MW_32),
    /* broadcasts */
    VEXI(vbroadcasti128, 2, 0x5a, 0, PP_66, 0, VF_BCAST, 0, 0, MW_16),
    VEXI(vbroadcasti32x4, 2, 0x5a, 0, PP_66, 0, VF_BCAST, 0, VX_EVEONLY, MW_16),
    VEXI(vbroadcastf64x2, 2, 0x1a, 0, PP_66, 1, VF_BCAST, 0, VX_EVEONLY, MW_16),
    VEXI(vpbroadcastd, 2, 0x58, 0, PP_66, 0, VF_BCAST, 0, 0, MW_4),
    VEXI(vpbroadcastq, 2, 0x59, 0x7c, PP_66, 1, VF_BCAST, 0, VX_SRCGPR | VX_W0VEX, MW_8),
    /* zeroing of the upper lanes */
    VEXI(vzeroupper, 1, 0x77, 0, 0, 0, VF_ZERO, 0, 0, MW_FULL),
    VEXI(vzeroall,   1, 0x77, 0, 0, 0, VF_ZERO, 1, 0, MW_FULL),
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 }
};

/* ModRM emission for the VEX path: the legacy asm_modrm logic with
   the register fields pre-masked by the caller (the extension bits
   live in the prefix, not in a REX) plus EVEX's compressed disp8*N
   form when eshift > 0: a numeric displacement divisible by
   (1 << eshift) whose quotient fits in int8 uses mod 01 with the
   quotient as the byte.  Symbolic and RIP-relative displacements
   are never scaled (their value is resolved at link time). */
static void asm_modrm_vex(int reg, Operand *op, int eshift)
{
    int mod, reg1, reg2, sib_reg1;

    if (!(op->type & OP_EA)) {
        /* register form */
        g(0xc0 + (reg << 3) + (op->reg & 7));
    } else if (op->reg == -1 && op->reg2 == -1) {
        /* displacement only */
        g(0x04 + (reg << 3));
        g(0x25);
        gen_expr32(&op->e);
    } else if (op->reg == -2) {
        /* RIP-relative */
        ExprValue *pe = &op->e;
        g(0x05 + (reg << 3));
        gen_addrpc32(pe->sym ? VT_SYM : 0, pe->sym, pe->v);
    } else {
        int64_t d = op->e.v, q = d;
        int scaled = 0;
        if (eshift && !op->e.sym && d % (1 << eshift) == 0) {
            q = d / (1 << eshift);
            scaled = 1;
        }
        sib_reg1 = op->reg;
        /* compute displacement encoding */
        if (sib_reg1 == -1) {
            sib_reg1 = 5;
            mod = 0x00;
        } else if (d == 0 && !op->e.sym && (op->reg & 7) != 5) {
            /* note: the base test uses the masked register (r13 is
               base 5 with the B extension bit, like rbp) */
            mod = 0x00;
        } else if (!op->e.sym && q == (int8_t)q && (scaled || !eshift)) {
            mod = 0x40;
        } else {
            mod = 0x80;
        }
        /* compute if sib byte needed */
        reg1 = op->reg;
        if (op->reg2 != -1)
            reg1 = 4;
        g(mod + (reg << 3) + (reg1 & 7));
        if ((reg1 & 7) == 4) {
            /* add sib byte */
            reg2 = op->reg2;
            if (reg2 == -1)
                reg2 = 4; /* indicate no index */
            g((op->shift << 6) + ((reg2 & 7) << 3) + (sib_reg1 & 7));
        }
        /* add offset */
        if (mod == 0x40) {
            g(q);
        } else if (mod == 0x80 || op->reg == -1) {
            gen_expr32(&op->e);
        }
    }
}

enum VexSM {
    VSM_OPERANDS, VSM_CLASSIFY, VSM_PREFIX, VSM_OPCODE,
    VSM_MODRM, VSM_IMM, VSM_DONE
};

/* Returns 1 when `opcode` is a VEX-family mnemonic (and has been
   fully handled or has errored), 0 when it is not ours. */
static int asm_opcode_vex(TCCState *s1, int opcode)
{
    const VEXInstr *vi;
    Operand ops[5];
    int mask[5], zero[5];
    int nb = 0, i, state;
    Operand *regop = NULL, *vvvvop = NULL, *rmop = NULL;
    Operand *immop = NULL, *is4op = NULL;
    int regnum = 0, vvvvnum = 0, rm_is_reg = 0;
    /* vvvvnum defaults to 0: with no vvvv operand the prefix field
       ~vvvv must read 1111 (the GAS encoding for vzeroupper, the
       two-operand moves, the permute-immediates and friends) */
    int ll = 0, w = 0, use_op2 = 0, regfield = 0;
    int pp_use = -1, opbyte = -1, kmov_gpr_w = -1;
    int w_override = -1, use_op3 = 0, force_evex = 0;
    int evex = 0, c5 = 0, eshift = 0;
    int ext_b = 0, ext_x = 0; /* rm/base and index extension facts */

    for (vi = vex_instrs; vi->sym != 0; vi++)
        if (vi->sym == opcode)
            break;
    if (vi->sym == 0)
        return 0;

    state = VSM_OPERANDS;
    while (state != VSM_DONE) {
        switch (state) {
        case VSM_OPERANDS: {
            for (;;) {
                if (tok == ';' || tok == TOK_LINEFEED)
                    break;
                if (nb >= 5)
                    tcc_error("incorrect number of operands");
                mask[nb] = -1;
                zero[nb] = 0;
                parse_operand(s1, &ops[nb]);
                if (ops[nb].type & OP_SEG)
                    tcc_error("segment prefix with VEX instruction");
                /* {%kN} / {z} decorations ride on the operand */
                while (tok == '{') {
                    next();
                    if (tok == '%') {
                        next();
                        if (tok < TOK_ASM_k0 || tok > TOK_ASM_k7)
                            tcc_error("expected mask register in decoration");
                        mask[nb] = tok - TOK_ASM_k0;
                        next();
                    } else if (tok >= TOK_IDENT && tok < tok_ident
                               && !strcmp(get_tok_str(tok, NULL), "z")) {
                        zero[nb] = 1;
                        next();
                    } else {
                        tcc_error("unsupported EVEX decoration");
                    }
                    if (tok != '}')
                        expect("}");
                    next();
                }
                nb++;
                if (tok != ',')
                    goto operands_done;
                next();
            }
        operands_done:
            state = VSM_CLASSIFY;
            break;
        }
        case VSM_CLASSIFY: {
            int want;
            /* dual-form mnemonics (vpermq and friends): pick the
               entry whose form class matches operand 0 */
            {
                const VEXInstr *cand = NULL, *alt = NULL, *vi2;
                int want_imm = nb > 0
                    && (ops[0].type & (OP_IM8 | OP_IM16 | OP_IM32 | OP_IM64));
                for (vi2 = vex_instrs; vi2->sym; vi2++) {
                    int imm_form;
                    if (vi2->sym != opcode)
                        continue;
                    imm_form = vi2->form == VF_NDS3I
                        || vi2->form == VF_PERMI
                        || vi2->form == VF_SHIFTI
                        || vi2->form == VF_KCMP
                        || vi2->form == VF_EXTRACT;
                    if (!alt)
                        alt = vi2;
                    if (imm_form == want_imm) {
                        cand = vi2;
                        break;
                    }
                }
                vi = cand ? cand : alt;
            }
            switch (vi->form) {
            case VF_ZERO: want = 0; break;
            case VF_MOV2: case VF_MOVDQ: case VF_MOVQ: case VF_BCAST: case VF_MOVMSK:
            case VF_KMOV:
                want = 2; break;
            case VF_EXTRACT: case VF_SHIFTI: case VF_PERMI:
                want = 3; break;
            case VF_NDS3: want = 3; break;
            case VF_NDS3I: case VF_IS4: case VF_KCMP:
                want = 4; break;
            default: want = -1; break;
            }
            if (nb != want)
                tcc_error("incorrect number of operands for '%s'",
                          get_tok_str(opcode, NULL));
            /* decorations are legal on the destination only, which
               in AT&T order is always the last operand written */
            for (i = 0; i + 1 < nb; i++)
                if (mask[i] >= 0 || zero[i])
                    tcc_error("EVEX decoration on a non-destination operand");
            if (nb > 0 && zero[nb - 1] && mask[nb - 1] < 0)
                tcc_error("{z} requires a writemask");
            pp_use = vi->pp;
            switch (vi->form) {
            case VF_KMOV: {
                /* exactly one side is the k register; the other is
                   a GPR or a memory reference.  Direction and the
                   opcode byte follow GAS's measured encodings. */
                Operand *kop, *other;
                int dir; /* 0: other -> k, 1: k -> other */
                if (ops[1].type & OP_KREG) {
                    kop = &ops[1]; other = &ops[0]; dir = 0;
                } else if (ops[0].type & OP_KREG) {
                    kop = &ops[0]; other = &ops[1]; dir = 1;
                } else {
                    tcc_error("'%s' needs a %%k register operand",
                              get_tok_str(opcode, NULL));
                    break;
                }
                if (nb > 0 && (mask[nb - 1] >= 0 || zero[nb - 1]))
                    tcc_error("'%s' takes no EVEX decoration",
                              get_tok_str(opcode, NULL));
                if (other->type & OP_EA) {
                    regop = kop; rmop = other;
                    opbyte = (dir ? vi->opcode2 : vi->opcode);
                } else if (other->type & OP_REG) {
                    pp_use = vi->ext & 3;
                    kmov_gpr_w = (vi->ext >> 7) & 1;
                    opbyte = (dir ? vi->opcode2 : vi->opcode) + 2;
                    if (dir) {
                        /* GPR store: GPR in ModRM.reg, k in rm */
                        regop = other; rmop = kop;
                    } else {
                        regop = kop; rmop = other;
                    }
                } else {
                    tcc_error("bad operand for '%s'",
                              get_tok_str(opcode, NULL));
                }
                break;
            }
            case VF_NDS3:
                if (vi->flags & VX_SWAPVV) {
                    vvvvop = &ops[0]; rmop = &ops[1];
                } else {
                    rmop = &ops[0]; vvvvop = &ops[1];
                }
                regop = &ops[2];
                break;
            case VF_NDS3I:
                immop = &ops[0]; rmop = &ops[1]; vvvvop = &ops[2];
                regop = &ops[3];
                break;
            case VF_IS4:
                /* GAS's blend syntax: the control register is the
                   FIRST source operand and travels in the IS4 byte */
                is4op = &ops[0]; rmop = &ops[1]; vvvvop = &ops[2];
                regop = &ops[3];
                break;
            case VF_KCMP:
                immop = &ops[0]; rmop = &ops[1]; vvvvop = &ops[2];
                regop = &ops[3];
                if (!(regop->type & OP_KREG))
                    tcc_error("mask compare destination must be a %%k register");
                break;
            case VF_MOV2:
                if (ops[1].type & OP_EA) {
                    if (!vi->opcode2)
                        tcc_error("'%s' has no store form",
                                  get_tok_str(opcode, NULL));
                    use_op2 = 1;
                    regop = &ops[0]; rmop = &ops[1];
                } else if ((ops[0].type & OP_VEC) && (ops[1].type & OP_VEC)
                           && !(ops[0].type & OP_ZMM) && vi->opcode2
                           && !(vi->flags & VX_EVEONLY)
                           && ops[0].reg >= 8 && ops[0].reg < 16
                           && ops[1].reg < 8
                           && mask[nb - 1] < 0) {
                    /* register-to-register with a high source: the
                       C5 form has no rm extension bit, so GAS flips
                       to the store opcode and carries the source in
                       the register field instead */
                    use_op2 = 1;
                    regop = &ops[0]; rmop = &ops[1];
                } else {
                    rmop = &ops[0]; regop = &ops[1];
                }
                break;
            case VF_MOVDQ:
                if ((ops[0].type & OP_VEC) && !(ops[1].type & OP_VEC)) {
                    /* a store: the second opcode;
                       register-to-register moves take the load form */
                    use_op2 = 1;
                    if (vi->ext) pp_use = vi->ext;
                    regop = &ops[0]; rmop = &ops[1];
                } else {
                    rmop = &ops[0]; regop = &ops[1];
                }
                break;
            case VF_MOVQ:
                /* GAS's four vmovq forms, measured byte for byte:
                   GPR->vec 66 6E W1, mem/vec->vec F3 7E W0,
                   vec->GPR 66 7E W1, vec->mem 66 D6 W0 (the W is a
                   VEX-only fact; EVEX keeps the entry's W) */
                if (ops[1].type & OP_VEC) {
                    regop = &ops[1]; rmop = &ops[0];
                    if (ops[0].type & OP_REG) {
                        pp_use = PP_66; w_override = 1;
                    } else {
                        use_op2 = 1; pp_use = PP_F3; w_override = 0;
                    }
                } else if (ops[0].type & OP_VEC) {
                    regop = &ops[0]; rmop = &ops[1];
                    if (ops[1].type & OP_REG) {
                        use_op2 = 1; pp_use = PP_66; w_override = 1;
                    } else {
                        use_op3 = 1; pp_use = PP_66; w_override = 0;
                    }
                } else
                    tcc_error("bad operands for 'vmovq'");
                break;
            case VF_BCAST:
                rmop = &ops[0]; regop = &ops[1];
                if (rmop->type & OP_REG) {
                    /* a general-register source is a different
                       opcode (vpbroadcastq %r10: 0x7c, not 0x59),
                       and that form exists only in EVEX encoding */
                    if (!vi->opcode2)
                        tcc_error("'%s' has no general-register source form",
                                  get_tok_str(opcode, NULL));
                    use_op2 = 1;
                    force_evex = 1;
                }
                break;
            case VF_MOVMSK:
                rmop = &ops[0]; regop = &ops[1];
                if (!(regop->type & OP_REG) || (regop->type & OP_EA))
                    tcc_error("movmsk destination must be a general register");
                break;
            case VF_EXTRACT:
                immop = &ops[0]; regop = &ops[1]; rmop = &ops[2];
                break;
            case VF_SHIFTI:
                immop = &ops[0]; rmop = &ops[1]; vvvvop = &ops[2];
                regop = NULL;
                break;
            case VF_PERMI:
                immop = &ops[0]; rmop = &ops[1]; regop = &ops[2];
                break;
            case VF_ZERO:
                break;
            }
            /* role validation (KMOV validated its own roles) */
            if (vi->form != VF_KMOV) {
            if (vi->flags & VX_GPR) {
                if (regop && !(regop->type & OP_REG))
                    tcc_error("'%s' needs general-purpose registers",
                              get_tok_str(opcode, NULL));
                if (vvvvop && !(vvvvop->type & OP_REG))
                    tcc_error("'%s' needs general-purpose registers",
                              get_tok_str(opcode, NULL));
            } else {
                if (regop && vi->form != VF_MOVMSK && vi->form != VF_KCMP
                    && !(regop->type & OP_VEC))
                    tcc_error("'%s' needs a vector register destination",
                              get_tok_str(opcode, NULL));
                if (vvvvop && !(vvvvop->type & OP_VEC))
                    tcc_error("'%s' needs a vector register source",
                              get_tok_str(opcode, NULL));
            }
            if (rmop && !(rmop->type & OP_EA) && !(rmop->type & OP_VEC)
                && !((rmop->type & OP_REG)
                     && ((vi->flags & (VX_RMGPR | VX_GPR | VX_SRCGPR))
                         || vi->form == VF_MOVDQ
                         || vi->form == VF_MOVQ)))
                tcc_error("bad rm operand for '%s'",
                          get_tok_str(opcode, NULL));
            }
            if (immop && !(immop->type
                           & (OP_IM8 | OP_IM8S | OP_IM16 | OP_IM32 | OP_IM64)))
                tcc_error("'%s' needs an immediate first operand",
                          get_tok_str(opcode, NULL));
            if (is4op && !(is4op->type & OP_VEC))
                tcc_error("blend control must be a vector register");
            /* vector width: the widest vector operand sets L/L'L */
            for (i = 0; i < nb; i++) {
                int wop = -1;
                if (ops[i].type & OP_ZMM) wop = 2;
                else if (ops[i].type & OP_YMM) wop = 1;
                else if (ops[i].type & OP_SSE) wop = 0;
                if (wop > ll) ll = wop;
            }
            /* extracts take L'L from the widest operand like
               everything else (GAS: vextracti64x2 from ymm carries
               L'L=01, from zmm L'L=10 — the SOURCE width) */
            /* equal widths on the plain three-operand ALU forms
               (the imm8 forms include inserts, whose widths differ
               by design, so they are not checked here) */
            if (vi->form == VF_NDS3 && !(vi->flags & VX_GPR)) {
                int wseen = -1;
                Operand *roles[3];
                roles[0] = rmop; roles[1] = vvvvop; roles[2] = regop;
                for (i = 0; i < 3; i++) {
                    int wop;
                    if (!roles[i] || (roles[i]->type & OP_EA))
                        continue;
                    wop = (roles[i]->type & OP_ZMM) ? 2
                        : (roles[i]->type & OP_YMM) ? 1 : 0;
                    if (wseen < 0) wseen = wop;
                    else if (wop != wseen)
                        tcc_error("vector width mismatch in '%s'",
                                  get_tok_str(opcode, NULL));
                }
            }
            if (regop) regnum = regop->reg;
            if (vvvvop) vvvvnum = vvvvop->reg;
            rm_is_reg = rmop && !(rmop->type & OP_EA);
            /* extension facts for the rm side */
            if (rmop) {
                if (rm_is_reg) {
                    ext_b = (rmop->reg >> 3) & 1;
                    ext_x = (rmop->reg >> 4) & 1;
                } else if (rmop->reg >= 0) {
                    ext_b = (rmop->reg >> 3) & 1;
                    if (rmop->reg2 >= 0)
                        ext_x = (rmop->reg2 >> 3) & 1;
                }
            }
            w = (vi->flags & VX_WGPR)
                ? !!(regop && (regop->type & OP_REG64)) : vi->w;
            if (kmov_gpr_w >= 0) w = kmov_gpr_w;
            /* prefix family selection */
            evex = 0;
            if (vi->flags & VX_EVEONLY) evex = 1;
            if (ll == 2) evex = 1;
            if (nb > 0 && (mask[nb - 1] >= 0 || zero[nb - 1])) evex = 1;
            if (regop && !(vi->flags & VX_GPR) && vi->form != VF_MOVMSK
                && regnum >= 16) evex = 1;
            if (vvvvop && vvvvnum >= 16) evex = 1;
            if (rm_is_reg && rmop->reg >= 16) evex = 1;
            if (vi->form == VF_KMOV) evex = 0; /* no EVEX kmov */
            if (vi->flags & VX_EVEXPREF) evex = 1;
            if (force_evex) evex = 1;
            if (w_override >= 0 && !evex) w = w_override;
            /* EVEX vmovq resolves differently from VEX (measured):
               loads take 66 6E, stores 66 7E, register moves keep
               the F3 7E form — all at the entry's W */
            if (vi->form == VF_MOVQ && evex) {
                if (ops[1].type & OP_VEC) {
                    if (ops[0].type & OP_VEC) {
                        use_op2 = 1; use_op3 = 0; pp_use = PP_F3;
                    } else {
                        use_op2 = 0; use_op3 = 0; pp_use = PP_66;
                    }
                } else {
                    use_op2 = 1; use_op3 = 0; pp_use = PP_66;
                }
            }
            /* GAS {vex} / {evex} line prefixes (tccasm.c records
               the request on the state) */
            if (s1->asm_vex_force == 1) {
                if ((vi->flags & VX_EVEONLY) || ll == 2 || force_evex
                    || regnum >= 16 || vvvvnum >= 16
                    || (rm_is_reg && rmop->reg >= 16)
                    || (nb > 0 && (mask[nb - 1] >= 0 || zero[nb - 1])))
                    tcc_error("{vex} cannot encode '%s' as written",
                              get_tok_str(opcode, NULL));
                evex = 0;
            } else if (s1->asm_vex_force == 2) {
                evex = 1;
            }
            if (!evex) {
                int wvex = (vi->flags & VX_W0VEX) ? 0 : w;
                c5 = vi->map == 1 && !wvex
                    && regnum < 16
                    && (!rmop || rm_is_reg
                        ? (!rmop || rmop->reg < 8)
                        : (rmop->reg < 8 && rmop->reg2 < 8));
                /* note: regnum < 16 always here (evex handled >= 16);
                   the C5 R bit covers reg 8..15, vvvv is 4 bits */
            }
            state = VSM_PREFIX;
            break;
        }
        case VSM_PREFIX: {
            int L = (vi->form == VF_ZERO) ? vi->ext : (ll == 1);
            /* address-size prefix, if an operand asked for one */
            for (i = 0; i < nb; i++)
                if (ops[i].type & OP_EA32) { g(0x67); break; }
            if (evex) {
                int aaa = nb > 0 && mask[nb - 1] >= 0 ? mask[nb - 1] : 0;
                int zb = nb > 0 ? zero[nb - 1] : 0;
                g(0x62);
                g(((~regnum >> 3) & 1) << 7 | (ext_x ? 0 : 0x40)
                  | (ext_b ? 0 : 0x20) | ((~regnum >> 4) & 1) << 4
                  | vi->map);
                g((w << 7) | ((~vvvvnum & 0xf) << 3) | 0x04 | pp_use);
                g((zb << 7) | (ll << 5) | ((~vvvvnum >> 4) & 1) << 3
                  | aaa);
            } else if (c5) {
                g(0xc5);
                g(((~regnum >> 3) & 1) << 7 | ((~vvvvnum & 0xf) << 3)
                  | (L << 2) | pp_use);
            } else {
                int wvex = (vi->flags & VX_W0VEX) ? 0 : w;
                g(0xc4);
                g(((~regnum >> 3) & 1) << 7 | (ext_x ? 0 : 0x40)
                  | (ext_b ? 0 : 0x20) | vi->map);
                g((wvex << 7) | ((~vvvvnum & 0xf) << 3) | (L << 2)
                  | pp_use);
            }
            state = VSM_OPCODE;
            break;
        }
        case VSM_OPCODE:
            g(opbyte >= 0 ? opbyte
              : use_op3 ? vi->ext
              : (use_op2 ? vi->opcode2 : vi->opcode));
            state = VSM_MODRM;
            break;
        case VSM_MODRM: {
            Operand mop;
            if (vi->form == VF_ZERO) {
                state = VSM_DONE;
                break;
            }
            regfield = vi->form == VF_SHIFTI ? vi->ext : (regnum & 7);
            mop = *rmop;
            if (evex) {
                switch (vi->mw) {
                case MW_4: eshift = 2; break;
                case MW_8: eshift = 3; break;
                case MW_16: eshift = 4; break;
                case MW_32: eshift = 5; break;
                default: eshift = 4 + ll; break; /* MW_FULL */
                }
            }
            asm_modrm_vex(regfield, &mop, eshift);
            state = VSM_IMM;
            break;
        }
        case VSM_IMM:
            if (vi->form == VF_IS4) {
                g((is4op->reg & 0xf) << 4);
            } else if (immop) {
                if (immop->e.sym)
                    tcc_error("immediate symbol in VEX instruction");
                g(immop->e.v);
            }
            state = VSM_DONE;
            break;
        default:
            state = VSM_DONE;
            break;
        }
    }
    return 1;
}

#endif /* TCC_TARGET_X86_64 */

ST_FUNC void asm_opcode(TCCState *s1, int opcode)
{
    const ASMInstr *pa;
#ifdef TCC_TARGET_X86_64
    if (asm_opcode_vex(s1, opcode))
        return;
#endif
    int i, modrm_index, modreg_index, reg, v, op1, seg_prefix, pc, p;
    int nb_ops, s;
    Operand ops[MAX_OPERANDS], *pop;
    int op_type[3]; /* decoded op type */
    int alltypes;   /* OR of all operand types */
    int autosize;
    int p66;
#ifdef TCC_TARGET_X86_64
    int rex64;
#endif

    maybe_print_stats();
    /* force synthetic ';' after prefix instruction, so we can handle */
    /* one-line things like "rep stosb" instead of only "rep\nstosb" */
    if (opcode >= TOK_ASM_wait && opcode <= TOK_ASM_repnz)
        unget_tok(';');

    /* get operands */
    pop = ops;
    nb_ops = 0;
    seg_prefix = 0;
    alltypes = 0;
    for(;;) {
        if (tok == ';' || tok == TOK_LINEFEED)
            break;
        if (nb_ops >= MAX_OPERANDS) {
            tcc_error("incorrect number of operands");
        }
        parse_operand(s1, pop);
        if (tok == ':') {
           if (!(pop->type & OP_SEG) || seg_prefix)
               tcc_error("incorrect prefix");
           seg_prefix = segment_prefixes[pop->reg];
           next();
           parse_operand(s1, pop);
           if (!(pop->type & OP_EA)) {
               tcc_error("segment prefix must be followed by memory reference");
           }
        }
        pop++;
        nb_ops++;
        if (tok != ',')
            break;
        next();
    }

    s = 0; /* avoid warning */

    /* F31: sal is the GAS spelling of the shl group (/4).  The
       shift span (rol..sar) has no sal tokens, so map the sal
       family onto shl before the table search. */
    if (opcode >= TOK_ASM_salb && opcode <= TOK_ASM_sal)
        opcode = TOK_ASM_shlb + (opcode - TOK_ASM_salb);

again:
    /* optimize matching by using a lookup table (no hashing is needed
       !) */
    for(pa = asm_instrs; pa->sym != 0; pa++) {
	int it = pa->instr_type & OPCT_MASK;
        s = 0;
        if (it == OPC_FARITH) {
            v = opcode - pa->sym;
            if (!((unsigned)v < 8 * 6 && (v % 6) == 0))
                continue;
        } else if (it == OPC_ARITH) {
            if (!(opcode >= pa->sym && opcode < pa->sym + 8*NBWLX))
                continue;
            s = (opcode - pa->sym) % NBWLX;
	    if ((pa->instr_type & OPC_BWLX) == OPC_WLX)
	      {
		/* We need to reject the xxxb opcodes that we accepted above.
		   Note that pa->sym for WLX opcodes is the 'w' token,
		   to get the 'b' token subtract one.  */
		if (((opcode - pa->sym + 1) % NBWLX) == 0)
		    continue;
	        s++;
	      }
        } else if (it == OPC_SHIFT) {
            if (!(opcode >= pa->sym && opcode < pa->sym + 7*NBWLX))
                continue;
            s = (opcode - pa->sym) % NBWLX;
        } else if (it == OPC_TEST) {
            if (!(opcode >= pa->sym && opcode < pa->sym + NB_TEST_OPCODES))
                continue;
	    /* cmovxx is a test opcode but accepts multiple sizes.
	       The suffixes aren't encoded in the table, instead we
	       simply force size autodetection always and deal with suffixed
	       variants below when we don't find e.g. "cmovzl".  */
	    if (pa->instr_type & OPC_WLX)
	        s = NBWLX - 1;
        } else if (pa->instr_type & OPC_B) {
#ifdef TCC_TARGET_X86_64
	    /* Some instructions don't have the full size but only
	       bwl form.  insb e.g. */
	    if ((pa->instr_type & OPC_WLQ) != OPC_WLQ
		&& !(opcode >= pa->sym && opcode < pa->sym + NBWLX-1))
	        continue;
#endif
            if (!(opcode >= pa->sym && opcode < pa->sym + NBWLX))
                continue;
            s = opcode - pa->sym;
        } else if (pa->instr_type & OPC_WLX) {
            if (!(opcode >= pa->sym && opcode < pa->sym + NBWLX-1))
                continue;
            s = opcode - pa->sym + 1;
        } else {
            if (pa->sym != opcode)
                continue;
        }
        if (pa->nb_ops != nb_ops)
            continue;
#ifdef TCC_TARGET_X86_64
	/* Special case for moves.  Selecting the IM64->REG64 form
	   should only be done if we really have an >32bit imm64, and that
	   is hardcoded.  Ignore it here.  */
	if (pa->opcode == 0xb0 && ops[0].type != OP_IM64
	    && (ops[1].type & OP_REG) == OP_REG64
	    && !(pa->instr_type & OPC_0F))
	    continue;
#endif
        /* now decode and check each operand */
	alltypes = 0;
        for(i = 0; i < nb_ops; i++) {
            int op1, op2;
            op1 = pa->op_type[i];
            op2 = op1 & 0x1f;
            switch(op2) {
            case OPT_IM:
                v = OP_IM8 | OP_IM16 | OP_IM32;
                break;
            case OPT_REG:
                v = OP_REG8 | OP_REG16 | OP_REG32 | OP_REG64;
                break;
            case OPT_REGW:
                v = OP_REG16 | OP_REG32 | OP_REG64;
                break;
            case OPT_IMW:
                v = OP_IM16 | OP_IM32;
                break;
	    case OPT_MMXSSE:
		v = OP_MMX | OP_SSE;
		break;
	    case OPT_DISP:
	    case OPT_DISP8:
		v = OP_ADDR;
		break;
            default:
                v = 1 << op2;
                break;
            }
            if (op1 & OPT_EA)
                v |= OP_EA;
	    op_type[i] = v;
            if ((ops[i].type & v) == 0)
                goto next;
	    alltypes |= ops[i].type;
        }
        (void)alltypes; /* maybe unused */
        /* all is matching ! */
        break;
    next: ;
    }
    if (pa->sym == 0) {
        if (opcode >= TOK_ASM_first && opcode <= TOK_ASM_last) {
            int b;
            b = op0_codes[opcode - TOK_ASM_first];
            if (b & 0xff00)
                g(b >> 8);
            g(b);
            return;
        } else if (opcode <= TOK_ASM_alllast) {
            tcc_error("bad operand with opcode '%s'",
                  get_tok_str(opcode, NULL));
        } else {
	    /* Special case for cmovcc, we accept size suffixes but ignore
	       them, but we don't want them to blow up our tables.  */
	    TokenSym *ts = table_ident[opcode - TOK_IDENT];
	    if (ts->len >= 6
		&& strchr("wlq", ts->str[ts->len-1])
		&& !memcmp(ts->str, "cmov", 4)) {
		opcode = tok_alloc(ts->str, ts->len-1)->tok;
		goto again;
	    }
            tcc_error("unknown opcode '%s'", ts->str);
        }
    }
    /* if the size is unknown, then evaluate it (OPC_B or OPC_WL case) */
    autosize = NBWLX-1;
#ifdef TCC_TARGET_X86_64
    /* XXX the autosize should rather be zero, to not have to adjust this
       all the time.  */
    if ((pa->instr_type & OPC_BWLQ) == OPC_B)
        autosize = NBWLX-2;
#endif
    if (s == autosize) {
	/* Check for register operands providing hints about the size.
	   Start from the end, i.e. destination operands.  This matters
	   only for opcodes accepting different sized registers, lar and lsl
	   are such opcodes.  */
        for(i = nb_ops - 1; s == autosize && i >= 0; i--) {
            if ((ops[i].type & OP_REG) && !(op_type[i] & (OP_CL | OP_DX)))
                s = reg_to_size[ops[i].type & OP_REG];
        }
        if (s == autosize) {
            if ((opcode == TOK_ASM_push || opcode == TOK_ASM_pop) &&
                (ops[0].type & (OP_SEG | OP_IM8S | OP_IM32)))
                s = 2;
	    else if ((opcode == TOK_ASM_push || opcode == TOK_ASM_pop) &&
		     (ops[0].type & OP_EA))
	        s = NBWLX - 2;
            else
                tcc_error("cannot infer opcode suffix");
        }
    }

#ifdef TCC_TARGET_X86_64
    rex64 = 0;
    if (pa->instr_type & OPC_48)
        rex64 = 1;
    else if (s == 3 || (alltypes & OP_REG64)) {
        /* generate REX prefix */
	int default64 = 0;
	for(i = 0; i < nb_ops; i++) {
	    if (op_type[i] == OP_REG64 && pa->opcode != 0xb8) {
		/* If only 64bit regs are accepted in one operand
		   this is a default64 instruction without need for
		   REX prefixes, except for movabs(0xb8).  */
		default64 = 1;
		break;
	    }
	}
	/* XXX find better encoding for the default64 instructions.  */
        if (((opcode != TOK_ASM_push && opcode != TOK_ASM_pop
	      && opcode != TOK_ASM_pushw && opcode != TOK_ASM_pushl
	      && opcode != TOK_ASM_pushq && opcode != TOK_ASM_popw
	      && opcode != TOK_ASM_popl && opcode != TOK_ASM_popq
	      && opcode != TOK_ASM_call && opcode != TOK_ASM_jmp))
	    && !default64)
            rex64 = 1;
    }
#endif

    /* now generates the operation */
    if (OPCT_IS(pa->instr_type, OPC_FWAIT))
        g(0x9b);
    if (seg_prefix)
        g(seg_prefix);
#ifdef TCC_TARGET_X86_64
    /* Generate addr32 prefix if needed */
    for(i = 0; i < nb_ops; i++) {
        if (ops[i].type & OP_EA32) {
	    g(0x67);
	    break;
        }
    }
#endif
    /* generate data16 prefix if needed */
    p66 = 0;
    if (s == 1)
        p66 = 1;
    else {
	/* accepting mmx+sse in all operands --> needs 0x66 to
	   switch to sse mode.  Accepting only sse in an operand --> is
	   already SSE insn and needs 0x66/f2/f3 handling.  */
        for (i = 0; i < nb_ops; i++)
            if ((op_type[i] & (OP_MMX | OP_SSE)) == (OP_MMX | OP_SSE)
	        && ops[i].type & OP_SSE)
	        p66 = 1;
    }
    if (p66)
        g(0x66);

    v = pa->opcode;
    p = v >> 8;  /* possibly prefix byte(s) */
    switch (p) {
        case 0: break;  /* no prefix */
        case 0x48: break; /* REX, handled elsewhere */
        case 0x66:
        case 0x67:
        case 0xf2:
        case 0xf3: v = v & 0xff; g(p); break;
        case 0xd4: case 0xd5: break; /* aam and aad, not prefix, but hardcoded immediate argument "10" */
        case 0xd8: case 0xd9: case 0xda: case 0xdb: /* x87, no normal prefix */
        case 0xdc: case 0xdd: case 0xde: case 0xdf: break;
        default: tcc_error("bad prefix 0x%2x in opcode table", p); break;
    }
    if (pa->instr_type & OPC_0F)
        v = ((v & ~0xff) << 8) | 0x0f00 | (v & 0xff);
    if (pa->instr_type & OPC_0F38)
        v = 0x0f3800 | (v & 0xff);
    if ((v == 0x69 || v == 0x6b) && nb_ops == 2) {
        /* kludge for imul $im, %reg */
        nb_ops = 3;
        ops[2] = ops[1];
        op_type[2] = op_type[1];
    } else if (v == 0xcd && ops[0].e.v == 3 && !ops[0].e.sym) {
        v--; /* int $3 case */
        nb_ops = 0;
    } else if ((v == 0x06 || v == 0x07)) {
        if (ops[0].reg >= 4) {
            /* push/pop %fs or %gs */
            v = 0x0fa0 + (v - 0x06) + ((ops[0].reg - 4) << 3);
        } else {
            v += ops[0].reg << 3;
        }
        nb_ops = 0;
    } else if (v <= 0x05) {
        /* arith case */
        v += ((opcode - TOK_ASM_addb) / NBWLX) << 3;
    } else if ((pa->instr_type & (OPCT_MASK | OPC_MODRM)) == OPC_FARITH) {
        /* fpu arith case */
        v += ((opcode - pa->sym) / 6) << 3;
    }

    /* search which operand will be used for modrm */
    modrm_index = -1;
    modreg_index = -1;
    if (pa->instr_type & OPC_MODRM) {
	if (!nb_ops) {
	    /* A modrm opcode without operands is a special case (e.g. mfence).
	       It has a group and acts as if there's an register operand 0 */
	    i = 0;
	    ops[i].type = OP_REG;
#ifdef TCC_TARGET_X86_64
	    if (pa->sym == TOK_ASM_endbr64)
	      ops[i].reg = 2; // dx
	    else if (pa->sym >= TOK_ASM_lfence && pa->sym <= TOK_ASM_sfence)
  	      ops[i].reg = 0; // ax
#else
	    if (pa->sym == TOK_ASM_endbr32)
	      ops[i].reg = 3; // bx
#endif
	    else
	      tcc_error("bad MODR/M opcode without operands");
	    goto modrm_found;
	}
        /* first look for an ea operand */
        for(i = 0;i < nb_ops; i++) {
            if (op_type[i] & OP_EA)
                goto modrm_found;
        }
        /* then if not found, a register or indirection (shift instructions) */
        for(i = 0;i < nb_ops; i++) {
            if (op_type[i] & (OP_REG | OP_MMX | OP_SSE | OP_INDIR))
                goto modrm_found;
        }
#ifdef ASM_DEBUG
        tcc_error("bad op table");
#endif
    modrm_found:
        modrm_index = i;
        /* if a register is used in another operand then it is
           used instead of group */
        for(i = 0;i < nb_ops; i++) {
            int t = op_type[i];
            if (i != modrm_index &&
                (t & (OP_REG | OP_MMX | OP_SSE | OP_CR | OP_TR | OP_DB | OP_SEG))) {
                modreg_index = i;
                break;
            }
        }
    }
#ifdef TCC_TARGET_X86_64
    asm_rex (rex64, ops, nb_ops, op_type, modreg_index, modrm_index);
#endif

    if (pa->instr_type & OPC_REG) {
        /* mov $im, %reg case */
        if (v == 0xb0 && s >= 1)
            v += 7;
        for(i = 0; i < nb_ops; i++) {
            if (op_type[i] & (OP_REG | OP_ST)) {
                v += ops[i].reg;
                break;
            }
        }
    }
    if (pa->instr_type & OPC_B)
        v += s >= 1;
    if (nb_ops == 1 && pa->op_type[0] == OPT_DISP8) {
	ElfSym *esym;
        int jmp_disp;

        /* see if we can really generate the jump with a byte offset */
	esym = elfsym(ops[0].e.sym);
        if (!esym || esym->st_shndx != cur_text_section->sh_num)
            goto no_short_jump;
        jmp_disp = ops[0].e.v + esym->st_value - ind - 2 - (v >= 0xff);
        if (jmp_disp == (int8_t)jmp_disp) {
            /* OK to generate jump */
	    ops[0].e.sym = 0;
            ops[0].e.v = jmp_disp;
	    op_type[0] = OP_IM8S;
        } else {
        no_short_jump:
	    /* long jump will be allowed. need to modify the
	       opcode slightly */
	    if (v == 0xeb) /* jmp */
	        v = 0xe9;
	    else if (v == 0x70) /* jcc */
	        v += 0x0f10;
	    else if (v == 0xe3 || v == 0x67e3) {
	        /* F31: jrcxz/jecxz have no long form.  GAS resolves a
	           forward target while assembling; TCC is one pass,
	           so the byte is emitted under an R_X86_64_PC8
	           relocation and resolved at link time, the same
	           deferral TCC already uses for a forward jmp. */
#ifdef TCC_TARGET_X86_64
	        greloca(cur_text_section, ops[0].e.sym,
	                ind + (v >= 0xff ? 2 : 1), R_X86_64_PC8, -1);
	        ops[0].e.sym = NULL;
	        ops[0].e.v = 0;
	        op_type[0] = OP_IM8S;
#else
	        tcc_error("invalid displacement");
#endif
	    }
	    else
	        tcc_error("invalid displacement");
        }
    }
    if (OPCT_IS(pa->instr_type, OPC_TEST))
        v += test_bits[opcode - pa->sym];
    else if (OPCT_IS(pa->instr_type, OPC_0F01))
        v |= 0x0f0100;
    op1 = v >> 16;
    if (op1)
        g(op1);
    op1 = (v >> 8) & 0xff;
    if (op1)
        g(op1);
    g(v);

    if (OPCT_IS(pa->instr_type, OPC_SHIFT)) {
        reg = (opcode - pa->sym) / NBWLX;
        if (reg == 6)
            reg = 7;
    } else if (OPCT_IS(pa->instr_type, OPC_ARITH)) {
        reg = (opcode - pa->sym) / NBWLX;
    } else if (OPCT_IS(pa->instr_type, OPC_FARITH)) {
        reg = (opcode - pa->sym) / 6;
    } else {
        reg = (pa->instr_type >> OPC_GROUP_SHIFT) & 7;
    }

    pc = 0;
    if (pa->instr_type & OPC_MODRM) {
        /* if a register is used in another operand then it is
           used instead of group */
	if (modreg_index >= 0)
	    reg = ops[modreg_index].reg;
        pc = asm_modrm(reg, &ops[modrm_index]);
    }

    /* emit constants */
#ifndef TCC_TARGET_X86_64
    if (!(pa->instr_type & OPC_0F)
	&& (pa->opcode == 0x9a || pa->opcode == 0xea)) {
        /* ljmp or lcall kludge */
	gen_expr32(&ops[1].e);
        if (ops[0].e.sym)
            tcc_error("cannot relocate");
        gen_le16(ops[0].e.v);
        return;
    }
#endif
    for(i = 0;i < nb_ops; i++) {
        v = op_type[i];
        if (v & (OP_IM8 | OP_IM16 | OP_IM32 | OP_IM64 | OP_IM8S | OP_ADDR)) {
            /* if multiple sizes are given it means we must look
               at the op size */
            if ((v | OP_IM8 | OP_IM64) == (OP_IM8 | OP_IM16 | OP_IM32 | OP_IM64)) {
                if (s == 0)
                    v = OP_IM8;
                else if (s == 1)
                    v = OP_IM16;
                else if (s == 2 || (v & OP_IM64) == 0)
                    v = OP_IM32;
                else
                    v = OP_IM64;
            }

            if ((v & (OP_IM8 | OP_IM8S | OP_IM16)) && ops[i].e.sym)
                tcc_error("cannot relocate");

            if (v & (OP_IM8 | OP_IM8S)) {
                g(ops[i].e.v);
            } else if (v & OP_IM16) {
                gen_le16(ops[i].e.v);
#ifdef TCC_TARGET_X86_64
            } else if (v & OP_IM64) {
                gen_expr64(&ops[i].e);
#endif
	    } else if (pa->op_type[i] == OPT_DISP || pa->op_type[i] == OPT_DISP8) {
                gen_disp32(&ops[i].e);
            } else {
                gen_expr32(&ops[i].e);
            }
        }
    }

    /* after immediate operands, adjust pc-relative address */
    if (pc)
        add32le(cur_text_section->data + pc - 4, pc - ind);
}

/* return the constraint priority (we allocate first the lowest
   numbered constraints) */
static inline int constraint_priority(const char *str)
{
    int priority, c, pr;

    /* we take the lowest priority */
    priority = 0;
    for(;;) {
        c = *str;
        if (c == '\0')
            break;
        str++;
        switch(c) {
        case 'A':
            pr = 0;
            break;
        case 'a':
        case 'b':
        case 'c':
        case 'd':
        case 'S':
        case 'D':
            pr = 1;
            break;
        case 'q':
            pr = 2;
            break;
        case 'r':
	case 'R':
	case 'p':
            pr = 3;
            break;
        case 'N':
        case 'M':
        case 'I':
	case 'e':
        case 'i':
        case 'm':
        case 'g':
            pr = 4;
            break;
        default:
            tcc_error("unknown constraint '%c'", c);
            pr = 0;
        }
        if (pr > priority)
            priority = pr;
    }
    return priority;
}

static const char *skip_constraint_modifiers(const char *p)
{
    while (*p == '=' || *p == '&' || *p == '+' || *p == '%')
        p++;
    return p;
}

/* If t (a token) is of the form "%reg" or "reg" return the register number and
   type, otherwise return -1. With GCC the % is optional, too. */
ST_FUNC int asm_parse_regvar (int t)
{
    const char *s;
    Operand op;
    if (t < TOK_IDENT || (t & SYM_FIELD))
        return -1;
    s = table_ident[t - TOK_IDENT]->str;
    if (s[0] == '%')
        ++s;
    t = tok_alloc_const(s);
    unget_tok(t);
    /* Internally the % prefix is required. */
    unget_tok('%');
    parse_operand(tcc_state, &op);
    /* Accept only integer regs for now. */
    if (op.type & OP_REG)
        return op.reg;
    else
        return -1;
}

#define REG_OUT_MASK 0x01
#define REG_IN_MASK  0x02

/* Number of general-purpose slots at the start of the clobber
   arrays; the remaining slots up to NB_ASM_REGS record SSE
   register clobbers (xmm0..), written by asm_clobber only. */
#ifdef TCC_TARGET_X86_64
# define NB_GP_REGS 16
#else
# define NB_GP_REGS 8
#endif

#define is_reg_allocated(reg) (regs_allocated[reg] & reg_mask)

ST_FUNC void asm_compute_constraints(ASMOperand *operands,
                                    int nb_operands, int nb_outputs,
                                    const uint8_t *clobber_regs,
                                    int *pout_reg)
{
    ASMOperand *op;
    int sorted_op[MAX_ASM_OPERANDS];
    int i, j, k, p1, p2, tmp, reg, c, reg_mask;
    const char *str;
    uint8_t regs_allocated[NB_ASM_REGS];

    /* init fields */
    for(i=0;i<nb_operands;i++) {
        op = &operands[i];
        op->input_index = -1;
        op->ref_index = -1;
        op->reg = -1;
        op->is_memory = 0;
        op->is_rw = 0;
    }
    /* compute constraint priority and evaluate references to output
       constraints if input constraints */
    for(i=0;i<nb_operands;i++) {
        op = &operands[i];
        str = op->constraint;
        str = skip_constraint_modifiers(str);
        if (isnum(*str) || *str == '[') {
            /* this is a reference to another constraint */
            k = find_constraint(operands, nb_operands, str, NULL);
            if ((unsigned)k >= i || i < nb_outputs)
                tcc_error("invalid reference in constraint %d ('%s')",
                      i, str);
            op->ref_index = k;
            if (operands[k].input_index >= 0)
                tcc_error("cannot reference twice the same operand");
            operands[k].input_index = i;
            op->priority = 5;
	} else if ((op->vt->r & VT_VALMASK) == VT_LOCAL
		   && op->vt->sym
		   && (reg = op->vt->sym->r & VT_VALMASK) < VT_CONST) {
	    op->priority = 1;
	    op->reg = reg;
        } else {
            op->priority = constraint_priority(str);
        }
    }

    /* sort operands according to their priority */
    for(i=0;i<nb_operands;i++)
        sorted_op[i] = i;
    for(i=0;i<nb_operands - 1;i++) {
        for(j=i+1;j<nb_operands;j++) {
            p1 = operands[sorted_op[i]].priority;
            p2 = operands[sorted_op[j]].priority;
            if (p2 < p1) {
                tmp = sorted_op[i];
                sorted_op[i] = sorted_op[j];
                sorted_op[j] = tmp;
            }
        }
    }

    for(i = 0;i < NB_ASM_REGS; i++) {
        if (clobber_regs[i])
            regs_allocated[i] = REG_IN_MASK | REG_OUT_MASK;
        else
            regs_allocated[i] = 0;
    }
    /* The SSE clobber slots are records, not allocatable
       registers: never hand them to an operand. */
    for(i = NB_GP_REGS; i < NB_ASM_REGS; i++)
        regs_allocated[i] = REG_IN_MASK | REG_OUT_MASK;
    /* esp cannot be used */
    regs_allocated[4] = REG_IN_MASK | REG_OUT_MASK;
    /* ebp cannot be used yet */
    regs_allocated[5] = REG_IN_MASK | REG_OUT_MASK;

    /* allocate registers and generate corresponding asm moves */
    for(i=0;i<nb_operands;i++) {
        j = sorted_op[i];
        op = &operands[j];
        str = op->constraint;
        /* no need to allocate references */
        if (op->ref_index >= 0)
            continue;
        /* select if register is used for output, input or both */
        if (op->input_index >= 0) {
            reg_mask = REG_IN_MASK | REG_OUT_MASK;
        } else if (j < nb_outputs) {
            reg_mask = REG_OUT_MASK;
        } else {
            reg_mask = REG_IN_MASK;
        }
	if (op->reg >= 0) {
	    if (is_reg_allocated(op->reg))
	        tcc_error("asm regvar requests register that's taken already");
	    reg = op->reg;
	}
    try_next:
        c = *str++;
        switch(c) {
        case '=':
            goto try_next;
        case '+':
            op->is_rw = 1;
            /* FALL THRU */
        case '&':
            if (j >= nb_outputs)
                tcc_error("'%c' modifier can only be applied to outputs", c);
            reg_mask = REG_IN_MASK | REG_OUT_MASK;
            goto try_next;
        case 'A':
            /* allocate both eax and edx */
            if (is_reg_allocated(TREG_XAX) ||
                is_reg_allocated(TREG_XDX))
                goto try_next;
            op->is_llong = 1;
            op->reg = TREG_XAX;
            regs_allocated[TREG_XAX] |= reg_mask;
            regs_allocated[TREG_XDX] |= reg_mask;
            break;
        case 'a':
            reg = TREG_XAX;
            goto alloc_reg;
        case 'b':
            reg = 3;
            goto alloc_reg;
        case 'c':
            reg = TREG_XCX;
            goto alloc_reg;
        case 'd':
            reg = TREG_XDX;
            goto alloc_reg;
        case 'S':
            reg = 6;
            goto alloc_reg;
        case 'D':
            reg = 7;
        alloc_reg:
            if (op->reg >= 0 && reg != op->reg)
                goto try_next;
            if (is_reg_allocated(reg))
                goto try_next;
            goto reg_found;
        case 'q':
            /* eax, ebx, ecx or edx */
            if (op->reg >= 0) {
                if ((reg = op->reg) < 4)
                    goto reg_found;
            } else for(reg = 0; reg < 4; reg++) {
                if (!is_reg_allocated(reg))
                    goto reg_found;
            }
            goto try_next;
        case 'r':
	case 'R':
	case 'p': /* A general address, for x86(64) any register is acceptable*/
            /* any general register */
            if ((reg = op->reg) >= 0)
                goto reg_found;
            else for(reg = 0; reg < NB_ASM_REGS; reg++) {
                if (!is_reg_allocated(reg))
                    goto reg_found;
            }
            goto try_next;
        reg_found:
            /* now we can reload in the register */
            op->is_llong = 0;
            op->reg = reg;
            regs_allocated[reg] |= reg_mask;
            break;
	case 'e':
        case 'i':
            if (!((op->vt->r & (VT_VALMASK | VT_LVAL)) == VT_CONST))
                goto try_next;
            break;
        case 'I':
        case 'N':
        case 'M':
            if (!((op->vt->r & (VT_VALMASK | VT_LVAL | VT_SYM)) == VT_CONST))
                goto try_next;
            break;
        case 'm':
        case 'g':
            /* nothing special to do because the operand is already in
               memory, except if the pointer itself is stored in a
               memory variable (VT_LLOCAL case) */
            /* XXX: fix constant case */
            /* if it is a reference to a memory zone, it must lie
               in a register, so we reserve the register in the
               input registers and a load will be generated
               later */
            if (j < nb_outputs || c == 'm') {
                if ((op->vt->r & VT_VALMASK) == VT_LLOCAL) {
                    /* any general register */
                    for(reg = 0; reg < NB_ASM_REGS; reg++) {
                        if (!(regs_allocated[reg] & REG_IN_MASK))
                            goto reg_found1;
                    }
                    goto try_next;
                reg_found1:
                    /* now we can reload in the register */
                    regs_allocated[reg] |= REG_IN_MASK;
                    op->reg = reg;
                    op->is_memory = 1;
                }
            }
            break;
        default:
            tcc_error("asm constraint %d ('%s') could not be satisfied",
                  j, op->constraint);
            break;
        }
        /* if a reference is present for that operand, we assign it too */
        if (op->input_index >= 0) {
            operands[op->input_index].reg = op->reg;
            operands[op->input_index].is_llong = op->is_llong;
        }
    }

    /* compute out_reg. It is used to store outputs registers to memory
       locations references by pointers (VT_LLOCAL case) */
    *pout_reg = -1;
    for(i=0;i<nb_operands;i++) {
        op = &operands[i];
        if (op->reg >= 0 &&
            (op->vt->r & VT_VALMASK) == VT_LLOCAL  &&
            !op->is_memory) {
            for(reg = 0; reg < NB_ASM_REGS; reg++) {
                if (!(regs_allocated[reg] & REG_OUT_MASK))
                    goto reg_found2;
            }
            tcc_error("could not find free output register for reloading");
        reg_found2:
            *pout_reg = reg;
            break;
        }
    }

    /* print sorted constraints */
#ifdef ASM_DEBUG
    for(i=0;i<nb_operands;i++) {
        j = sorted_op[i];
        op = &operands[j];
        printf("%%%d [%s]: \"%s\" r=0x%04x reg=%d\n",
               j,
               op->id ? get_tok_str(op->id, NULL) : "",
               op->constraint,
               op->vt->r,
               op->reg);
    }
    if (*pout_reg >= 0)
        printf("out_reg=%d\n", *pout_reg);
#endif
}

ST_FUNC void subst_asm_operand(CString *add_str,
                              SValue *sv, int modifier)
{
    int r, reg, size, val;

    r = sv->r;
    if ((r & VT_VALMASK) == VT_CONST) {
        if (!(r & VT_LVAL) && modifier != 'c' && modifier != 'n' &&
	    modifier != 'P')
            cstr_ccat(add_str, '$');
        if (r & VT_SYM) {
	    const char *name = get_tok_str(sv->sym->v, NULL);
	    if (sv->sym->v >= SYM_FIRST_ANOM) {
		/* In case of anonymous symbols ("L.42", used
		   for static data labels) we can't find them
		   in the C symbol table when later looking up
		   this name.  So enter them now into the asm label
		   list when we still know the symbol.  */
		get_asm_sym(tok_alloc_const(name), sv->sym);
	    }
            if (tcc_state->leading_underscore)
              cstr_ccat(add_str, '_');
            cstr_cat(add_str, name, -1);
            if ((uint32_t)sv->c.i == 0)
                goto no_offset;
	    cstr_ccat(add_str, '+');
        }
        val = sv->c.i;
        if (modifier == 'n')
            val = -val;
        cstr_printf(add_str, "%d", val);
    no_offset:;
#ifdef TCC_TARGET_X86_64
        if (r & VT_LVAL)
            cstr_cat(add_str, "(%rip)", -1);
#endif
    } else if ((r & VT_VALMASK) == VT_LOCAL) {
        cstr_printf(add_str, "%d(%%%s)", (int)sv->c.i, get_tok_str(TOK_ASM_xax + 5, NULL));
    } else if (r & VT_LVAL) {
        reg = r & VT_VALMASK;
        if (reg >= VT_CONST)
            tcc_internal_error("");
        cstr_printf(add_str, "(%%%s)", get_tok_str(TOK_ASM_xax + reg, NULL));
    } else {
        /* register case */
        reg = r & VT_VALMASK;
        if (reg >= VT_CONST)
            tcc_internal_error("");

        /* choose register operand size */
        if ((sv->type.t & VT_BTYPE) == VT_BYTE ||
	    (sv->type.t & VT_BTYPE) == VT_BOOL)
            size = 1;
        else if ((sv->type.t & VT_BTYPE) == VT_SHORT)
            size = 2;
#ifdef TCC_TARGET_X86_64
        else if ((sv->type.t & VT_BTYPE) == VT_LLONG ||
		 (sv->type.t & VT_BTYPE) == VT_PTR)
            size = 8;
#endif
        else
            size = 4;
        if (size == 1 && reg >= 4)
            size = 4;

        if (modifier == 'b') {
            if (reg >= 4)
                tcc_error("cannot use byte register");
            size = 1;
        } else if (modifier == 'h') {
            if (reg >= 4)
                tcc_error("cannot use byte register");
            size = -1;
        } else if (modifier == 'w') {
            size = 2;
        } else if (modifier == 'k') {
            size = 4;
#ifdef TCC_TARGET_X86_64
        } else if (modifier == 'q') {
            size = 8;
#endif
        }

        if (reg >= 8) {
            cstr_printf(add_str, "%%r%d%c", reg, (size == 1) ? 'b' : ((size == 2) ? 'w' : ((size == 4) ? 'd' : ' ')));
            return;
        }
        switch(size) {
        case -1:
            reg = TOK_ASM_ah + reg;
            break;
        case 1:
            reg = TOK_ASM_al + reg;
            break;
        case 2:
            reg = TOK_ASM_ax + reg;
            break;
        default:
            reg = TOK_ASM_eax + reg;
            break;
#ifdef TCC_TARGET_X86_64
        case 8:
            reg = TOK_ASM_rax + reg;
            break;
#endif
        }
        cstr_printf(add_str, "%%%s", get_tok_str(reg, NULL));
    }
}

/* generate prolog and epilog code for asm statement */
ST_FUNC void asm_gen_code(ASMOperand *operands, int nb_operands,
                         int nb_outputs, int is_output,
                         uint8_t *clobber_regs,
                         int out_reg)
{
    uint8_t regs_allocated[NB_ASM_REGS];
    ASMOperand *op;
    int i, reg;

    /* Strictly speaking %Xbp and %Xsp should be included in the
       call-preserved registers, but currently it doesn't matter.  */
#ifdef TCC_TARGET_X86_64
#ifdef TCC_TARGET_PE
    static const uint8_t reg_saved[] = { 3, 6, 7, 12, 13, 14, 15 };
#else
    static const uint8_t reg_saved[] = { 3, 12, 13, 14, 15 };
#endif
#else
    static const uint8_t reg_saved[] = { 3, 6, 7 };
#endif

    /* mark all used registers */
    memcpy(regs_allocated, clobber_regs, sizeof(regs_allocated));
    for(i = 0; i < nb_operands;i++) {
        op = &operands[i];
        if (op->reg >= 0)
            regs_allocated[op->reg] = 1;
    }
    if (!is_output) {
        /* generate reg save code */
        for(i = 0; i < sizeof(reg_saved)/sizeof(reg_saved[0]); i++) {
            reg = reg_saved[i];
            if (regs_allocated[reg]) {
		if (reg >= 8)
		  g(0x41), reg-=8;
                g(0x50 + reg);
            }
        }

        /* generate load code */
        for(i = 0; i < nb_operands; i++) {
            op = &operands[i];
            if (op->reg >= 0) {
                if ((op->vt->r & VT_VALMASK) == VT_LLOCAL &&
                    op->is_memory) {
                    /* memory reference case (for both input and
                       output cases) */
                    SValue sv;
                    sv = *op->vt;
                    sv.r = (sv.r & ~VT_VALMASK) | VT_LOCAL | VT_LVAL;
                    sv.type.t = VT_PTR;
                    load(op->reg, &sv);
                } else if (i >= nb_outputs || op->is_rw) {
                    /* load value in register */
                    load(op->reg, op->vt);
                    if (op->is_llong) {
                        SValue sv;
                        sv = *op->vt;
                        sv.c.i += 4;
                        load(TREG_XDX, &sv);
                    }
                }
            }
        }
    } else {
        /* generate save code */
        for(i = 0 ; i < nb_outputs; i++) {
            op = &operands[i];
            if (op->reg >= 0) {
                if ((op->vt->r & VT_VALMASK) == VT_LLOCAL) {
                    if (!op->is_memory) {
                        SValue sv;
                        sv = *op->vt;
                        sv.r = (sv.r & ~VT_VALMASK) | VT_LOCAL;
			sv.type.t = VT_PTR;
                        load(out_reg, &sv);

			sv = *op->vt;
                        sv.r = (sv.r & ~VT_VALMASK) | out_reg;
                        store(op->reg, &sv);
                    }
                } else {
                    store(op->reg, op->vt);
                    if (op->is_llong) {
                        SValue sv;
                        sv = *op->vt;
                        sv.c.i += 4;
                        store(TREG_XDX, &sv);
                    }
                }
            }
        }
        /* generate reg restore code */
        for(i = sizeof(reg_saved)/sizeof(reg_saved[0]) - 1; i >= 0; i--) {
            reg = reg_saved[i];
            if (regs_allocated[reg]) {
		if (reg >= 8)
		  g(0x41), reg-=8;
                g(0x58 + reg);
            }
        }
    }
}

ST_FUNC void asm_clobber(uint8_t *clobber_regs, const char *str)
{
    int reg;
    const char *s = str;
#ifdef TCC_TARGET_X86_64
    unsigned int type;
#endif

    if (!strcmp(str, "memory") ||
        !strcmp(str, "cc") ||
	!strcmp(str, "flags"))
        return;
    if (s[0] == '%')
        s++; /* GCC accepts the register name with or without '%' */
    if (!strncmp(s, "xmm", 3) && s[3]) {
        /* SSE register clobber (F12): recorded above the general
           registers.  TCC's allocator never keeps C values in xmm
           registers across an asm statement, so -- exactly as for
           "cc" -- recording is the whole obligation; the marking
           also keeps asm_compute_constraints from ever treating
           the slot as free. */
        char *end;
        long n = strtol(s + 3, &end, 10);
        if (*end == '\0' && n >= 0 && n < NB_ASM_REGS - NB_GP_REGS) {
            clobber_regs[NB_GP_REGS + n] = 1;
            return;
        }
        tcc_error("invalid clobber register '%s'", str);
    }
    if (s[0] == 'm' && s[1] == 'm' && s[2] >= '0' && s[2] <= '7'
        && s[3] == '\0')
        /* MMX register clobber: accepted; neither backend ever
           allocates MMX registers, so there is nothing to record
           (same class as "cc"). */
        return;
    reg = tok_alloc_const(s);
    if (reg >= TOK_ASM_eax && reg <= TOK_ASM_edi) {
        reg -= TOK_ASM_eax;
    } else if (reg >= TOK_ASM_ax && reg <= TOK_ASM_di) {
        reg -= TOK_ASM_ax;
#ifdef TCC_TARGET_X86_64
    } else if (reg >= TOK_ASM_rax && reg <= TOK_ASM_rdi) {
        reg -= TOK_ASM_rax;
    } else if ((reg = asm_parse_numeric_reg(reg, &type)) >= 0) {
	;
#endif
    } else {
        tcc_error("invalid clobber register '%s'", str);
    }
    clobber_regs[reg] = 1;
}
