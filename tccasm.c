/*
 *  GAS like assembler for TCC
 * 
 *  Copyright (c) 2001-2004 Fabrice Bellard
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
#ifdef CONFIG_TCC_ASM

static Section *last_text_section; /* to handle .previous asm directive */
static int asmgoto_n;

static int tcc_assemble_internal(TCCState *s1, int do_preprocess, int global);
static Sym* asm_new_label(TCCState *s1, int label, int is_local);
static Sym* asm_new_label1(TCCState *s1, int label, int is_local, int sh_num, int value);

#if PTR_SIZE == 8
/* output constant with relocation if 'r & VT_SYM' is true */
ST_FUNC void gen_addr64(int r, Sym *sym, int64_t c)
{
    if (r & VT_SYM)
        greloca(cur_text_section, sym, ind, R_DATA_PTR, c), c=0;
    gen_le32(c);
    gen_le32(c>>32);
}

ST_FUNC void gen_expr64(ExprValue *pe)
{
    if (pe->sym && asm_label_diff_emit(pe->sym, pe->v, 8)) {
        /* deferred label difference: zero field, patched later */
        gen_le32(0);
        gen_le32(0);
        return;
    }
    gen_addr64(pe->sym ? VT_SYM : 0, pe->sym, pe->v);
}
#endif

static int asm_get_prefix_name(TCCState *s1, const char *prefix, unsigned int n)
{
    char buf[64];
    snprintf(buf, sizeof(buf), "%s%u", prefix, n);
    return tok_alloc_const(buf);
}

ST_FUNC int asm_get_local_label_name(TCCState *s1, unsigned int n)
{
    return asm_get_prefix_name(s1, "L..", n);
}

/* If a C name has an _ prepended then only asm labels that start
   with _ are representable in C, by removing the first _.  ASM names
   without _ at the beginning don't correspond to C names, but we use
   the global C symbol table to track ASM names as well, so we need to
   transform those into ones that don't conflict with a C name,
   so prepend a '.' for them, but force the ELF asm name to be set.  */
static int asm2cname(int v, int *addeddot)
{
    const char *name;
    *addeddot = 0;
    if (!tcc_state->leading_underscore)
      return v;
    name = get_tok_str(v, NULL);
    if (!name)
      return v;
    if (name[0] == '_') {
        v = tok_alloc_const(name + 1);
    } else if (!strchr(name, '.')) {
        char newname[256];
        snprintf(newname, sizeof newname, ".%s", name);
        v = tok_alloc_const(newname);
        *addeddot = 1;
    }
    return v;
}

static Sym *asm_label_find(int v)
{
    Sym *sym;
    int addeddot;
    v = asm2cname(v, &addeddot);
    sym = sym_find(v);
    while (sym && sym->sym_scope && !(sym->type.t & VT_STATIC))
        sym = sym->prev_tok;
    return sym;
}

static Sym *asm_label_push(int v)
{
    int addeddot, v2 = asm2cname(v, &addeddot);
    /* We always add VT_EXTERN, for sym definition that's tentative
       (for .set, removed for real defs), for mere references it's correct
       as is.  */
    Sym *sym = global_identifier_push(v2, VT_ASM | VT_EXTERN | VT_STATIC, 0);
    if (addeddot)
        sym->asm_label = v;
    return sym;
}

/* Return a symbol we can use inside the assembler, having name NAME.
   Symbols from asm and C source share a namespace.  If we generate
   an asm symbol it's also a (file-global) C symbol, but it's
   either not accessible by name (like "L.123"), or its type information
   is such that it's not usable without a proper C declaration.

   Sometimes we need symbols accessible by name from asm, which
   are anonymous in C, in this case CSYM can be used to transfer
   all information from that symbol to the (possibly newly created)
   asm symbol.  */
ST_FUNC Sym* get_asm_sym(int name, Sym *csym)
{
    Sym *sym = asm_label_find(name);
    if (!sym) {
	sym = asm_label_push(name);
	if (csym)
	  sym->c = csym->c;
    }
    return sym;
}

static Sym* asm_section_sym(TCCState *s1, Section *sec)
{
    char buf[100]; int label; Sym *sym;
    snprintf(buf, sizeof buf, "L.%s", sec->name);
    label = tok_alloc_const(buf);
    sym = asm_label_find(label);
    return sym ? sym : asm_new_label1(s1, label, 1, sec->sh_num, 0);
}

/* ------------------------------------------------------------------ */
/* Deferred label differences (F12).
 *
 * GAS resolves "labelA - labelB" once both labels are known to lie
 * in the same section, even when one or both are still undefined at
 * the point of use; the perlasm ABI-note tail (".long 1f - 0f"
 * written ahead of its labels) is the canonical case.  TCC's
 * evaluator folds label differences eagerly, so asm_expr_sum() now
 * turns such a subtraction into a synthetic symbol standing for the
 * difference.  The data emitters (gen_expr32/gen_expr64) recognise
 * it through asm_label_diff_emit(), emit a zero field and register
 * a patch; asm_label_diffs_apply() fills the fields in once the
 * assembly unit is complete and every label has its final value.
 * A difference whose labels do not end up defined in one common
 * section is rejected there.  Only the x86 assemblers defer; on
 * other targets the subtraction keeps its historical error (see
 * asm_expr_diff_defer). */
typedef struct LabelDiff {
    Sym *sym;                   /* synthetic symbol for (a - b) */
    Sym *a, *b;
} LabelDiff;

typedef struct LabelDiffPatch {
    Section *sec;               /* section holding the field */
    unsigned long offset;
    int size;                   /* field size in bytes (4 or 8) */
    Sym *a, *b;
    int64_t addend;             /* constant part of the expression */
} LabelDiffPatch;

static LabelDiff **label_diffs;
static int nb_label_diffs;
static LabelDiffPatch **label_diff_patches;
static int nb_label_diff_patches;
static int label_diff_counter;

static void asm_label_diffs_reset(void)
{
    dynarray_reset(&label_diffs, &nb_label_diffs);
    dynarray_reset(&label_diff_patches, &nb_label_diff_patches);
    label_diff_counter = 0;
}

static Sym *asm_label_diff_new(TCCState *s1, Sym *a, Sym *b)
{
    LabelDiff *d = tcc_malloc(sizeof(LabelDiff));
    d->a = a;
    d->b = b;
    d->sym = asm_label_push(asm_get_prefix_name(s1, "L..diff",
                                                label_diff_counter++));
    dynarray_add(&label_diffs, &nb_label_diffs, d);
    return d->sym;
}

static LabelDiff *asm_label_diff_find(Sym *sym)
{
    int i;
    if (!sym)
        return NULL;
    for (i = 0; i < nb_label_diffs; i++)
        if (label_diffs[i]->sym == sym)
            return label_diffs[i];
    return NULL;
}

ST_FUNC int asm_label_diff_is(Sym *sym)
{
    return asm_label_diff_find(sym) != NULL;
}

/* If SYM stands for a deferred label difference, register a patch
   for the field of SIZE bytes about to be emitted at the current
   position and return 1; otherwise return 0. */
ST_FUNC int asm_label_diff_emit(Sym *sym, int64_t addend, int size)
{
    LabelDiff *d = asm_label_diff_find(sym);
    LabelDiffPatch *p;
    if (!d)
        return 0;
    p = tcc_malloc(sizeof(LabelDiffPatch));
    p->sec = cur_text_section;
    p->offset = ind;
    p->size = size;
    p->a = d->a;
    p->b = d->b;
    p->addend = addend;
    dynarray_add(&label_diff_patches, &nb_label_diff_patches, p);
    return 1;
}

static void asm_label_diffs_apply(void)
{
    int i, j;
    for (i = 0; i < nb_label_diff_patches; i++) {
        LabelDiffPatch *p = label_diff_patches[i];
        ElfSym *ea = elfsym(p->a), *eb = elfsym(p->b);
        int64_t v;
        uint8_t *ptr;
        if (!ea || !eb || ea->st_shndx == SHN_UNDEF
            || eb->st_shndx == SHN_UNDEF)
            tcc_error("label difference involves an undefined label");
        if (ea->st_shndx != eb->st_shndx)
            tcc_error("label difference across sections");
        v = (int64_t)ea->st_value - (int64_t)eb->st_value + p->addend;
        if (p->sec->sh_type == SHT_NOBITS)
            continue; /* cannot happen: NOBITS emits no fields */
        ptr = p->sec->data + p->offset;
        for (j = 0; j < p->size; j++)
            ptr[j] = (uint64_t)v >> (8 * j);
    }
}

/* If PE - E2 is the difference of two assembler labels, replace
   PE's symbol by a synthetic symbol standing for the difference
   (resolved at the end of the unit) and return 1. */
static int asm_expr_diff_defer(TCCState *s1, ExprValue *pe, ExprValue *e2)
{
#if defined(TCC_TARGET_I386) || defined(TCC_TARGET_X86_64)
    if (pe->sym && e2->sym && IS_ASM_SYM(pe->sym) && IS_ASM_SYM(e2->sym)) {
        pe->sym = asm_label_diff_new(s1, pe->sym, e2->sym);
        pe->pcrel = 0;
        return 1;
    }
#endif
    return 0;
}

/* ------------------------------------------------------------------ */
/* .comm bookkeeping (F12): .comm allocations are deferred to the
   end of the assembly unit so repeated directives merge with GAS
   semantics (largest size and alignment win); this record holds
   the merged extents per symbol (see TOK_ASMDIR_comm). */
typedef struct CommDef {
    int v;                      /* symbol name token */
    long size, align;
} CommDef;

static CommDef **comm_defs;
static int nb_comm_defs;

static CommDef *asm_comm_find(int v)
{
    int i;
    for (i = 0; i < nb_comm_defs; i++)
        if (comm_defs[i]->v == v)
            return comm_defs[i];
    return NULL;
}

static void asm_comm_record(int v, long size, long align)
{
    CommDef *cd = tcc_malloc(sizeof(CommDef));
    cd->v = v;
    cd->size = size;
    cd->align = align;
    dynarray_add(&comm_defs, &nb_comm_defs, cd);
}

static void asm_comm_reset(void)
{
    dynarray_reset(&comm_defs, &nb_comm_defs);
}

/* Materialise this unit's .comm symbols with their merged extents. */
static void asm_comms_apply(TCCState *s1)
{
    int i;
    for (i = 0; i < nb_comm_defs; i++) {
        CommDef *cd = comm_defs[i];
        Sym *sym = asm_label_find(cd->v);
        ElfSym *esym = elfsym(sym);
        if (!esym || (esym->st_shndx != SHN_UNDEF
                      && esym->st_shndx != SHN_COMMON))
            tcc_error("symbol '%s' was defined after its .comm",
                      get_tok_str(cd->v, NULL));
        if (s1->nocommon) {
            addr_t addr = section_add(bss_section, cd->size, cd->align);
            put_extern_sym(sym, bss_section, addr, cd->size);
        } else {
            /* for SHN_COMMON the symbol value is the alignment */
            put_extern_sym(sym, common_section, cd->align, cd->size);
        }
        esym = elfsym(sym);
        esym->st_info = ELFW(ST_INFO)(ELFW(ST_BIND)(esym->st_info),
                                      STT_OBJECT);
    }
}

/* We do not use the C expression parser to handle symbols. Maybe the
   C expression parser could be tweaked to do so. */

static void asm_expr_unary(TCCState *s1, ExprValue *pe)
{
    Sym *sym;
    int op, label;
    uint64_t n;
    const char *p;

    switch(tok) {
    case TOK_PPNUM:
        p = tokc.str.data;
        n = strtoull(p, (char **)&p, 0);
        if (*p == 'b' || *p == 'f') {
            /* backward or forward label */
            label = asm_get_local_label_name(s1, n);
            sym = asm_label_find(label);
            if (*p == 'b') {
                /* backward : find the last corresponding defined label */
                if (sym && (!sym->c || elfsym(sym)->st_shndx == SHN_UNDEF))
                    sym = sym->prev_tok;
                if (!sym)
                    tcc_error("local label '%d' not found backward", (int)n);
            } else {
                /* forward */
                if (!sym || (sym->c && elfsym(sym)->st_shndx != SHN_UNDEF)) {
                    /* if the last label is defined, then define a new one */
		    sym = asm_label_push(label);
                }
            }
	    pe->v = 0;
	    pe->sym = sym;
	    pe->pcrel = 0;
        } else if (*p == '\0') {
            pe->v = n;
            pe->sym = NULL;
	    pe->pcrel = 0;
        } else {
            tcc_error("invalid number syntax");
        }
        next();
        break;
    case '+':
        next();
        asm_expr_unary(s1, pe);
        break;
    case '-':
    case '~':
        op = tok;
        next();
        asm_expr_unary(s1, pe);
        if (pe->sym)
            tcc_error("invalid operation with label");
        if (op == '-')
            pe->v = -pe->v;
        else
            pe->v = ~pe->v;
        break;
    case TOK_CCHAR:
    case TOK_LCHAR:
	pe->v = tokc.i;
	pe->sym = NULL;
	pe->pcrel = 0;
	next();
	break;
    case '(':
        next();
        asm_expr(s1, pe);
        skip(')');
        break;
    case '.':
        pe->v = ind;
        pe->sym = asm_section_sym(s1, cur_text_section);
        pe->pcrel = 0;
        next();
        break;
    default:
        if (tok >= TOK_IDENT) {
	    ElfSym *esym;
            /* label case : if the label was not found, add one */
	    sym = get_asm_sym(tok, NULL);
	    esym = elfsym(sym);
            if (esym && esym->st_shndx == SHN_ABS) {
                /* if absolute symbol, no need to put a symbol value */
                pe->v = esym->st_value;
                pe->sym = NULL;
		pe->pcrel = 0;
            } else {
                pe->v = 0;
                pe->sym = sym;
		pe->pcrel = 0;
            }
            next();
        } else {
            tcc_error("bad expression syntax [%s]", get_tok_str(tok, &tokc));
        }
        break;
    }
}
    
static void asm_expr_prod(TCCState *s1, ExprValue *pe)
{
    int op;
    ExprValue e2;

    asm_expr_unary(s1, pe);
    for(;;) {
        op = tok;
        if (op != '*' && op != '/' && op != '%' && 
            op != TOK_SHL && op != TOK_SAR)
            break;
        next();
        asm_expr_unary(s1, &e2);
        if (pe->sym || e2.sym)
            tcc_error("invalid operation with label");
        switch(op) {
        case '*':
            pe->v *= e2.v;
            break;
        case '/':  
            if (e2.v == 0) {
            div_error:
                tcc_error("division by zero");
            }
            pe->v /= e2.v;
            break;
        case '%':  
            if (e2.v == 0)
                goto div_error;
            pe->v %= e2.v;
            break;
        case TOK_SHL:
            pe->v <<= e2.v;
            break;
        default:
        case TOK_SAR:
            pe->v >>= e2.v;
            break;
        }
    }
}

static void asm_expr_logic(TCCState *s1, ExprValue *pe)
{
    int op;
    ExprValue e2;

    asm_expr_prod(s1, pe);
    for(;;) {
        op = tok;
        if (op != '&' && op != '|' && op != '^')
            break;
        next();
        asm_expr_prod(s1, &e2);
        if (pe->sym || e2.sym)
            tcc_error("invalid operation with label");
        switch(op) {
        case '&':
            pe->v &= e2.v;
            break;
        case '|':  
            pe->v |= e2.v;
            break;
        default:
        case '^':
            pe->v ^= e2.v;
            break;
        }
    }
}

static inline void asm_expr_sum(TCCState *s1, ExprValue *pe)
{
    int op;
    ExprValue e2;

    asm_expr_logic(s1, pe);
    for(;;) {
        op = tok;
        if (op != '+' && op != '-')
            break;
        next();
        asm_expr_logic(s1, &e2);
        if (op == '+') {
            if (pe->sym != NULL && e2.sym != NULL)
                goto cannot_relocate;
            pe->v += e2.v;
            if (pe->sym == NULL && e2.sym != NULL)
                pe->sym = e2.sym;
        } else {
            pe->v -= e2.v;
            /* NOTE: we are less powerful than gas in that case
               because we store only one symbol in the expression */
	    if (!e2.sym) {
		/* OK */
	    } else if (pe->sym == e2.sym) { 
		/* OK */
		pe->sym = NULL; /* same symbols can be subtracted to NULL */
	    } else {
		ElfSym *esym1, *esym2;
		esym1 = elfsym(pe->sym);
		esym2 = elfsym(e2.sym);
		if (esym2 && esym1 && esym1->st_shndx == esym2->st_shndx
		    && esym1->st_shndx != SHN_UNDEF) {
		    /* we also accept defined symbols in the same section */
		    pe->v += (int)(esym1->st_value - esym2->st_value);
		    pe->sym = NULL;
		} else if (esym2 && esym2->st_shndx == cur_text_section->sh_num) {
		    /* When subtracting a defined symbol in current section
		       this actually makes the value PC-relative.  */
		    pe->v += (int)(0 - esym2->st_value);
		    pe->pcrel = 1;
		    e2.sym = NULL;
		} else if (asm_expr_diff_defer(s1, pe, &e2)) {
		    /* deferred label difference: pe->sym now stands for
		       the difference, resolved at end of the unit */
		} else {
cannot_relocate:
		    tcc_error("invalid operation with label");
		}
	    }
        }
    }
}

static inline void asm_expr_cmp(TCCState *s1, ExprValue *pe)
{
    int op;
    ExprValue e2;

    asm_expr_sum(s1, pe);
    for(;;) {
        op = tok;
	if (op != TOK_EQ && op != TOK_NE
	    && (op > TOK_GT || op < TOK_ULE))
            break;
        next();
        asm_expr_sum(s1, &e2);
        if (pe->sym || e2.sym)
            tcc_error("invalid operation with label");
        switch(op) {
	case TOK_EQ:
	    pe->v = pe->v == e2.v;
	    break;
	case TOK_NE:
	    pe->v = pe->v != e2.v;
	    break;
	case TOK_LT:
	    pe->v = (int64_t)pe->v < (int64_t)e2.v;
	    break;
	case TOK_GE:
	    pe->v = (int64_t)pe->v >= (int64_t)e2.v;
	    break;
	case TOK_LE:
	    pe->v = (int64_t)pe->v <= (int64_t)e2.v;
	    break;
	case TOK_GT:
	    pe->v = (int64_t)pe->v > (int64_t)e2.v;
	    break;
        default:
            break;
        }
	/* GAS compare results are -1/0 not 1/0.  */
	pe->v = -(int64_t)pe->v;
    }
}

ST_FUNC void asm_expr(TCCState *s1, ExprValue *pe)
{
    asm_expr_cmp(s1, pe);
}

ST_FUNC int asm_int_expr(TCCState *s1)
{
    ExprValue e;
    asm_expr(s1, &e);
    if (e.sym)
        expect("constant");
    if ((int)e.v != e.v)
	tcc_error("integer out of range %lld", (long long)e.v);
    return e.v;
}

static Sym* asm_new_label1(TCCState *s1, int label, int is_local,
                           int sh_num, int value)
{
    Sym *sym;
    ElfSym *esym;

    sym = asm_label_find(label);
    if (sym) {
	esym = elfsym(sym);
	/* A VT_EXTERN symbol, even if it has a section is considered
	   overridable.  This is how we "define" .set targets.  Real
	   definitions won't have VT_EXTERN set.  */
        if (esym && esym->st_shndx != SHN_UNDEF) {
            /* the label is already defined */
            if (IS_ASM_SYM(sym)
                && (is_local == 1 || (sym->type.t & VT_EXTERN)))
                goto new_label;
            if (!(sym->type.t & VT_EXTERN))
                tcc_error("assembler label '%s' already defined",
                          get_tok_str(label, NULL));
        }
    } else {
    new_label:
        sym = asm_label_push(label);
    }
    if (!sym->c)
      put_extern_sym2(sym, SHN_UNDEF, 0, 0, 1);
    esym = elfsym(sym);
    esym->st_shndx = sh_num;
    esym->st_value = value;
    if (is_local != 2)
        sym->type.t &= ~VT_EXTERN;
    return sym;
}

static Sym* asm_new_label(TCCState *s1, int label, int is_local)
{
    return asm_new_label1(s1, label, is_local, cur_text_section->sh_num, ind);
}

/* Set the value of LABEL to that of some expression (possibly
   involving other symbols).  LABEL can be overwritten later still.  */
static Sym* set_symbol(TCCState *s1, int label)
{
    long n;
    ExprValue e;
    Sym *sym;
    ElfSym *esym;
    next();
    asm_expr(s1, &e);
    n = e.v;
    esym = elfsym(e.sym);
    if (esym)
	n += esym->st_value;
    sym = asm_new_label1(s1, label, 2, esym ? esym->st_shndx : SHN_ABS, n);
    elfsym(sym)->st_other |= ST_ASM_SET;
    return sym;
}

static void use_section1(TCCState *s1, Section *sec)
{
    cur_text_section->data_offset = ind;
    cur_text_section = sec;
    ind = cur_text_section->data_offset;
}

static void use_section(TCCState *s1, const char *name)
{
    Section *sec;
    sec = find_section(s1, name);
    use_section1(s1, sec);
}

static void push_section(TCCState *s1, const char *name)
{
    Section *sec = find_section(s1, name);
    sec->prev = cur_text_section;
    use_section1(s1, sec);
}

static void pop_section(TCCState *s1)
{
    Section *prev = cur_text_section->prev;
    if (!prev)
        tcc_error(".popsection without .pushsection");
    cur_text_section->prev = NULL;
    use_section1(s1, prev);
}

/* CFI directive operands (F9): parsed and shape-validated, then discarded.
   TCC builds .eh_frame only from its own C-level debug info (tccdbg.c);
   unwind annotations in hand-written assembler carry no information the
   code generator can use, so -- like GAS sources assembled for a consumer
   that ignores them -- they are accepted and dropped.  Malformed operands
   are still errors: nothing here may silently derail the token stream.
   Register operands are checked for kind ([%]name or DWARF number), not
   for existence on the target, since the value is not emitted. */
static void asm_cfi_reg(TCCState *s1)
{
    if (tok == '%')
        next();
    if (tok == TOK_PPNUM) {
        /* DWARF register number (aarch64/riscv compiler output) */
        next();
        return;
    }
    if (tok >= TOK_IDENT) {
        next();
        return;
    }
    tcc_error("register expected in .cfi directive");
}

static void asm_cfi_name(TCCState *s1)
{
    /* a symbol name, possibly dotted (DW.ref.__gxx_personality_v0),
       a local label (.Lfoo), or 0 for "none" (.cfi_personality) */
    if (tok == TOK_PPNUM) {
        next();
        return;
    }
    if (tok == '.')
        next();
    if (tok < TOK_IDENT)
        tcc_error("symbol expected in .cfi directive");
    next();
    while (tok == '.') {
        next();
        if (tok < TOK_IDENT)
            tcc_error("symbol expected in .cfi directive");
        next();
    }
}

static void asm_parse_directive(TCCState *s1, int global)
{
    int n, offset, v, size, tok1, c;
    Section *sec;
    uint8_t *ptr;

    /* assembler directive */
    sec = cur_text_section;
    switch(tok) {
    case TOK_ASMDIR_align:
    case TOK_ASMDIR_balign:
    case TOK_ASMDIR_p2align:
    case TOK_ASMDIR_skip:
    case TOK_ASMDIR_space:
        tok1 = tok;
        next();
        n = asm_int_expr(s1);
        if (tok1 == TOK_ASMDIR_p2align)
        {
            if (n < 0 || n > 30)
                tcc_error("invalid p2align, must be between 0 and 30");
            n = 1 << n;
            tok1 = TOK_ASMDIR_align;
        }
        if (tok1 == TOK_ASMDIR_align || tok1 == TOK_ASMDIR_balign) {
            if (n <= 0 || (n & (n-1)) != 0)
                tcc_error("alignment must be a positive power of two");
            offset = (ind + n - 1) & -n;
            size = offset - ind;
            /* the section must have a compatible alignment */
            if (sec->sh_addralign < n)
                sec->sh_addralign = n;
            c = sec->sh_flags & SHF_EXECINSTR;
        } else {
	    if (n < 0)
	        n = 0;
            size = n, c = 0;
        }
        v = 0;
        if (tok == ',') {
            next();
            v = asm_int_expr(s1), c = 0;
        }
    zero_pad:
	if ((uint64_t)ind + size >= 1<<30)
	    tcc_error("too much data");
        if (sec->sh_type != SHT_NOBITS) {
            if (c) {
                gen_fill_nops(size);
                break;
            }
            sec->data_offset = ind;
            ptr = section_ptr_add(sec, size);
            memset(ptr, v, size);
        }
        ind += size;
        break;
    case TOK_ASMDIR_quad:
#if PTR_SIZE == 8
	size = 8;
	goto asm_data;
#else
        next();
        for(;;) {
            uint64_t vl;
            const char *p;

            p = tokc.str.data;
            if (tok != TOK_PPNUM) {
            error_constant:
                tcc_error("64 bit constant");
            }
            vl = strtoll(p, (char **)&p, 0);
            if (*p != '\0')
                goto error_constant;
            next();
            if (sec->sh_type != SHT_NOBITS) {
                /* XXX: endianness */
                gen_le32(vl);
                gen_le32(vl >> 32);
            } else {
                ind += 8;
            }
            if (tok != ',')
                break;
            next();
        }
        break;
#endif
    case TOK_ASMDIR_byte:
        size = 1;
        goto asm_data;
    case TOK_ASMDIR_word:
    case TOK_ASMDIR_short:
        size = 2;
        goto asm_data;
    case TOK_ASMDIR_long:
    case TOK_ASMDIR_int:
        size = 4;
    asm_data:
        next();
        for(;;) {
            ExprValue e;
            asm_expr(s1, &e);
            if (sec->sh_type != SHT_NOBITS) {
                if (size == 4) {
                    gen_expr32(&e);
#if PTR_SIZE == 8
		} else if (size == 8) {
		    gen_expr64(&e);
#endif
                } else {
                    if (e.sym)
                        expect("constant");
                    if (size == 1)
                        g(e.v);
                    else
                        gen_le16(e.v);
                }
            } else {
                ind += size;
            }
            if (tok != ',')
                break;
            next();
        }
        break;
    case TOK_ASMDIR_fill:
        {
            int repeat, size, val, i, j;
            uint8_t repeat_buf[8];
            next();
            repeat = asm_int_expr(s1);
            if (repeat < 0) {
                tcc_error("repeat < 0; .fill ignored");
                break;
            }
            size = 1;
            val = 0;
            if (tok == ',') {
                next();
                size = asm_int_expr(s1);
                if (size < 0) {
                    tcc_error("size < 0; .fill ignored");
                    break;
                }
                if (size > 8)
                    size = 8;
                if (tok == ',') {
                    next();
                    val = asm_int_expr(s1);
                }
            }
            /* XXX: endianness */
            repeat_buf[0] = val;
            repeat_buf[1] = val >> 8;
            repeat_buf[2] = val >> 16;
            repeat_buf[3] = val >> 24;
            repeat_buf[4] = 0;
            repeat_buf[5] = 0;
            repeat_buf[6] = 0;
            repeat_buf[7] = 0;
            for(i = 0; i < repeat; i++) {
                for(j = 0; j < size; j++) {
                    g(repeat_buf[j]);
                }
            }
        }
        break;
    case TOK_ASMDIR_rept:
        {
            int repeat;
            TokenString *init_str;
            next();
            repeat = asm_int_expr(s1);
            init_str = tok_str_alloc();
            while (next(), tok != TOK_ASMDIR_endr) {
                if (tok == CH_EOF)
                    tcc_error("we at end of file, .endr not found");
                tok_str_add_tok(init_str);
            }
            tok_str_add(init_str, TOK_EOF);
            begin_macro(init_str, 1);
            while (repeat-- > 0) {
                tcc_assemble_internal(s1, (parse_flags & PARSE_FLAG_PREPROCESS),
				      global);
                macro_ptr = init_str->str;
            }
            end_macro();
            next();
            break;
        }
    case TOK_ASMDIR_org:
        {
	    ExprValue e;
	    ElfSym *esym;
            next();
	    asm_expr(s1, &e);
	    n = e.v;
	    esym = elfsym(e.sym);
	    if (esym) {
		if (esym->st_shndx != cur_text_section->sh_num)
		  expect("constant or same-section symbol");
		n += esym->st_value;
	    }
            if (n < ind)
                tcc_error("attempt to .org backwards");
            v = c = 0;
            size = n - ind;
            goto zero_pad;
        }
        break;
    case TOK_ASMDIR_set:
	next();
	tok1 = tok;
	next();
	/* Also accept '.set stuff', but don't do anything with this.
	   It's used in GAS to set various features like '.set mips16'.  */
	if (tok == ',')
	    set_symbol(s1, tok1);
	break;
    case TOK_ASMDIR_globl:
    case TOK_ASMDIR_global:
    case TOK_ASMDIR_weak:
    case TOK_ASMDIR_hidden:
	tok1 = tok;
	do { 
            Sym *sym;
            next();
	    if (tok < TOK_IDENT)
		expect("identifier");
            sym = get_asm_sym(tok, NULL);
	    if (tok1 != TOK_ASMDIR_hidden)
                sym->type.t &= ~VT_STATIC;
            if (tok1 == TOK_ASMDIR_weak)
                sym->a.weak = 1;
	    else if (tok1 == TOK_ASMDIR_hidden)
	        sym->a.visibility = STV_HIDDEN;
            update_storage(sym);
            next();
	} while (tok == ',');
	break;
    case TOK_ASMDIR_string:
    case TOK_ASMDIR_ascii:
    case TOK_ASMDIR_asciz:
        {
            const char *p;
            int i, size, t;

            t = tok;
            next();
            for(;;) {
                if (tok != TOK_STR)
                    expect("string constant");
                p = tokc.str.data;
                size = tokc.str.size;
                if (t == TOK_ASMDIR_ascii && size > 0)
                    size--;
                for(i = 0; i < size; i++)
                    g(p[i]);
                next();
                if (tok == ',') {
                    next();
                } else if (tok != TOK_STR) {
                    break;
                }
            }
	}
	break;
    case TOK_ASMDIR_text:
    case TOK_ASMDIR_data:
    case TOK_ASMDIR_bss:
	{ 
            char sname[64];
            tok1 = tok;
            n = 0;
            next();
            if (tok != ';' && tok != TOK_LINEFEED) {
		n = asm_int_expr(s1);
		next();
            }
            if (n)
                sprintf(sname, "%s%d", get_tok_str(tok1, NULL), n);
            else
                sprintf(sname, "%s", get_tok_str(tok1, NULL));
            use_section(s1, sname);
	}
	break;
    case TOK_ASMDIR_comm:
        {
            Sym *sym;
            ElfSym *esym;
            long size, align;
            int name_tok;
            next();
            if (tok < TOK_IDENT)
                expect("identifier");
            name_tok = tok;
            sym = get_asm_sym(tok, NULL);
            next();
            skip(',');
            size = asm_int_expr(s1);
            if (size < 0)
                tcc_error("invalid size in .comm");
            if (tok == ',') {
                next();
                align = asm_int_expr(s1);
                if (align <= 0 || (align & (align - 1)) != 0)
                    tcc_error("alignment in .comm is not a power of two");
            } else {
                /* GAS default alignment: the smallest power of
                   two >= size, capped at 16 */
                align = 1;
                while (align < size && align < 16)
                    align <<= 1;
            }
            /* .comm symbols are global even without .globl and
               typed OBJECT.  The allocation itself is deferred to
               the end of the unit (asm_comms_apply) so that
               repeated .comm directives merge exactly like GAS --
               largest size and alignment win -- in both modes:
               SHN_COMMON under -fcommon (the symbol value carries
               the alignment), .bss under -fno-common (tcc's
               default), exactly like C tentative definitions. */
            sym->type.t &= ~VT_STATIC;
            esym = elfsym(sym);
            if (esym && esym->st_shndx == SHN_COMMON) {
                /* a common from an earlier unit (e.g. C): fold
                   its extents into the merge */
                if ((long)esym->st_size > size)
                    size = esym->st_size;
                if ((long)esym->st_value > align)
                    align = esym->st_value;
            } else if (esym && esym->st_shndx != SHN_UNDEF) {
                tcc_error("symbol '%s' is already defined",
                          get_tok_str(sym->v, NULL));
            }
            {
                CommDef *cd = asm_comm_find(name_tok);
                if (cd) {
                    if (size > cd->size)
                        cd->size = size;
                    if (align > cd->align)
                        cd->align = align;
                } else {
                    asm_comm_record(name_tok, size, align);
                }
            }
            if (!sym->c)
                /* an undefined ELF entry now, so relocations in
                   this unit can reference the symbol */
                put_extern_sym2(sym, SHN_UNDEF, 0, 0, 1);
        }
        break;
    case TOK_ASMDIR_file:
        {
            const char *p;
            parse_flags &= ~PARSE_FLAG_TOK_STR;
            next();
            if (tok == TOK_PPNUM)
                next();
            if (tok == TOK_PPSTR && tokc.str.data[0] == '"') {
                tokc.str.data[tokc.str.size - 2] = 0;
                p = tokc.str.data + 1;
            } else if (tok >= TOK_IDENT) {
                p = get_tok_str(tok, &tokc);
            } else {
                skip_to_eol(0);
                break;
            }
            tccpp_putfile(p);
            next();
        }
        break;
    case TOK_ASMDIR_ident:
        {
            char ident[256];

            ident[0] = '\0';
            next();
            if (tok == TOK_STR)
                pstrcat(ident, sizeof(ident), tokc.str.data);
            else
                pstrcat(ident, sizeof(ident), get_tok_str(tok, &tokc));
            tcc_warning_c(warn_unsupported)("ignoring .ident %s", ident);
            next();
        }
        break;
    case TOK_ASMDIR_size:
        { 
            Sym *sym;
            ElfSym *esym;

            next();
	    if (tok < TOK_IDENT)
		expect("identifier");
            sym = asm_label_find(tok);
            if (!sym)
                tcc_error("label not found: %s", get_tok_str(tok, NULL));
            /* XXX .size name,label2-label1 */
            tcc_warning_c(warn_unsupported)("ignoring .size %s,*", get_tok_str(tok, NULL));
            next();
            skip(',');
            n = asm_int_expr(s1);
            esym = elfsym(sym);
            if (esym) {
                esym->st_size = n;
            }
        }
        break;
    case TOK_ASMDIR_type:
        { 
            Sym *sym;
            const char *newtype;
            int st_type;

            next();
	    if (tok < TOK_IDENT)
		expect("identifier");
            sym = get_asm_sym(tok, NULL);
            next();
            skip(',');
            if (tok == TOK_STR) {
                newtype = tokc.str.data;
            } else {
                if (tok == '@' || tok == '%')
                    next();
                newtype = get_tok_str(tok, NULL);
            }

            if (!strcmp(newtype, "function") || !strcmp(newtype, "STT_FUNC")) {
                if (IS_ASM_SYM(sym))
                    sym->type.t |= VT_ASM_FUNC;
                st_type = STT_FUNC;
            set_st_type:
                if (sym->c) {
                    ElfSym *esym = elfsym(sym);
                    esym->st_info = ELFW(ST_INFO)(ELFW(ST_BIND)(esym->st_info), st_type);
                }
            } else if (!strcmp(newtype, "object") || !strcmp(newtype, "STT_OBJECT")) {
                st_type = STT_OBJECT;
                goto set_st_type;
            } else
                tcc_warning_c(warn_unsupported)("change type of '%s' from 0x%x to '%s' ignored",
                    get_tok_str(sym->v, NULL), sym->type.t, newtype);

            next();
        }
        break;
    case TOK_ASMDIR_pushsection:
    case TOK_ASMDIR_section:
        {
            char sname[256];
	    int old_nb_section = s1->nb_sections;
            int flags = SHF_ALLOC; /* TCC's longstanding default for
                              an option-less directive; code in the
                              wild (and tcctest's .data.ignore)
                              relies on the section being allocated.
                              A flags string, when present, replaces
                              it from zero, exactly as in GAS. */
            int sh_type = -1;
            long sh_entsize = -1;
            int opt_stage = 0; /* 0: flags, 1: type/entsize, 2: group */

	    tok1 = tok;
            next();
            sname[0] = '\0';
            while (tok != ';' && tok != TOK_LINEFEED && tok != ',') {
                if (tok == TOK_STR)
                    pstrcat(sname, sizeof(sname), tokc.str.data);
                else
                    pstrcat(sname, sizeof(sname), get_tok_str(tok, NULL));
                next();
            }
            /* GAS option grammar (F12):
                 .section name [, "flags"] [, @type] [, entsize]
                             [, groupname [, comdat]]
               A '#' after the comma starts a comment on x86 targets,
               so a tail like perlasm's ", #alloc" carries no flags
               for GAS on x86-64 either (verified with GAS+readelf);
               it simply ends the option list. */
            while (tok == ',') {
                next();
                if (tok == TOK_LINEFEED || tok == ';' || tok == TOK_EOF)
                    /* A '#' comment (already consumed by the
                       tokenizer, which treats '#' as comment-to-EOL
                       in asm files) or the plain end of the line:
                       no options follow. */
                    break;
                if (tok == '#') {
                    while (tok != ';' && tok != TOK_LINEFEED
                           && tok != TOK_EOF)
                        next();
                    break;
                }
                if (opt_stage == 0) {
                    /* The flags string: one SHF bit per letter,
                       unknown letters are an error, as in GAS. */
                    const char *p;
                    if (tok != TOK_STR)
                        expect("string constant");
                    flags = 0;
                    for (p = tokc.str.data; *p; ++p) {
                        switch (*p) {
                        case 'a': flags |= SHF_ALLOC; break;
                        case 'w': flags |= SHF_WRITE; break;
                        case 'x': flags |= SHF_EXECINSTR; break;
                        case 'M': flags |= SHF_MERGE; break;
                        case 'S': flags |= SHF_STRINGS; break;
                        case 'T': flags |= SHF_TLS; break;
                        case 'G': flags |= SHF_GROUP; break;
                        case 'e': flags |= SHF_EXCLUDE; break;
                        case 'o': break; /* SHF_OS_NONCONFORMING:
                                            no state to record */
                        default:
                            tcc_error("unknown section flag '%c'", *p);
                        }
                    }
                    opt_stage = 1;
                    next();
                } else if (opt_stage == 1 && (tok == '@' || tok == '%')) {
                    const char *tname;
                    next();
                    if (tok < TOK_IDENT)
                        expect("section type");
                    tname = get_tok_str(tok, NULL);
                    if (!strcmp(tname, "progbits"))
                        sh_type = SHT_PROGBITS;
                    else if (!strcmp(tname, "nobits"))
                        sh_type = SHT_NOBITS;
                    else if (!strcmp(tname, "note"))
                        sh_type = SHT_NOTE;
                    else if (!strcmp(tname, "init_array"))
                        sh_type = SHT_INIT_ARRAY;
                    else if (!strcmp(tname, "fini_array"))
                        sh_type = SHT_FINI_ARRAY;
                    else if (!strcmp(tname, "preinit_array"))
                        sh_type = SHT_PREINIT_ARRAY;
                    else
                        tcc_error("unknown section type '%s'", tname);
                    opt_stage = 2;
                    next();
                } else if (opt_stage >= 1 && opt_stage <= 2
                           && tok == TOK_PPNUM && sh_entsize < 0) {
                    sh_entsize = asm_int_expr(s1);
                    opt_stage = 2;
                } else if (opt_stage == 2 && tok == TOK_STR) {
                    /* Group name: accepted and shape-validated, but
                       TCC emits no SHT_GROUP section for it. */
                    opt_stage = 3;
                    next();
                } else if (opt_stage == 3 && tok >= TOK_IDENT
                           && !strcmp(get_tok_str(tok, NULL), "comdat")) {
                    opt_stage = 4;
                    next();
                } else {
                    expect("section option");
                }
            }
            last_text_section = cur_text_section;
	    if (tok1 == TOK_ASMDIR_section)
	        use_section(s1, sname);
	    else
	        push_section(s1, sname);
	    /* If we just allocated a new section reset its alignment to
	       1.  new_section normally acts for GCC compatibility and
	       sets alignment to PTR_SIZE.  The assembler behaves different. */
	    if (old_nb_section != s1->nb_sections) {
	        cur_text_section->sh_addralign = 1;
                /* Make .init and .fini sections executable by default.
                   GAS does so, too, and musl relies on it. */
                if (!strcmp(sname, ".init") || !strcmp(sname, ".fini"))
                    flags |= SHF_EXECINSTR;
	        cur_text_section->sh_flags = flags;
                if (sh_type >= 0)
                    cur_text_section->sh_type = sh_type;
                else if (!strncmp(sname, ".note", 5)
                         && (sname[5] == '\0' || sname[5] == '.'))
                    /* GAS types sections named .note[.xxx] SHT_NOTE
                       by default (e.g. .note.gnu.property). */
                    cur_text_section->sh_type = SHT_NOTE;
                if (sh_entsize < 0
                    && (sh_type == SHT_INIT_ARRAY
                        || sh_type == SHT_FINI_ARRAY
                        || sh_type == SHT_PREINIT_ARRAY))
                    /* GAS records the natural entry size for the
                       array-of-pointers section types. */
                    sh_entsize = PTR_SIZE;
                if (sh_entsize > 0)
                    cur_text_section->sh_entsize = sh_entsize;
            }
        }
        break;
    case TOK_ASMDIR_previous:
        { 
            Section *sec;
            next();
            if (!last_text_section)
                tcc_error("no previous section referenced");
            sec = cur_text_section;
            use_section1(s1, last_text_section);
            last_text_section = sec;
        }
        break;
    case TOK_ASMDIR_popsection:
	next();
	pop_section(s1);
	break;
#ifdef TCC_TARGET_I386
    case TOK_ASMDIR_code16:
        {
            next();
            s1->seg_size = 16;
        }
        break;
    case TOK_ASMDIR_code32:
        {
            next();
            s1->seg_size = 32;
        }
        break;
#endif
#if PTR_SIZE == 8
    /* added for compatibility with GAS */
    case TOK_ASMDIR_code64:
        next();
        break;
#endif
#ifdef TCC_TARGET_RISCV64
    case TOK_ASMDIR_option:
        next();
        switch(tok){
            case TOK_ASM_rvc:    /* Will be deprecated soon in favor of arch */
            case TOK_ASM_norvc:  /* Will be deprecated soon in favor of arch */
            case TOK_ASM_pic:
            case TOK_ASM_nopic:
            case TOK_ASM_relax:
            case TOK_ASM_norelax:
            case TOK_ASM_push:
            case TOK_ASM_pop:
                /* TODO: unimplemented */
                next();
                break;
            case TOK_ASM_arch:
                /* TODO: unimplemented, requires extra parsing */
                tcc_error("unimp .option '.%s'", get_tok_str(tok, NULL));
                break;
            default:
                tcc_error("unknown .option '.%s'", get_tok_str(tok, NULL));
                break;
        }
        break;
#endif
    /* TODO: Implement symvar support. FreeBSD >= 14 needs this */
    case TOK_ASMDIR_symver:
	next();
	next();
        skip(',');
	next();
        skip('@');
	next();
	break;
    case TOK_ASMDIR_reloc:
	{
	    ExprValue e;
	    const char *reloc_name;
	    int reloc_type = -1;

	    next();
	    asm_expr(s1, &e);
	    skip(',');
	    reloc_name = get_tok_str(tok, NULL);
#if defined(TCC_TARGET_ARM64)
	    if (!strcmp(reloc_name, "R_AARCH64_CALL26"))
	        reloc_type = R_AARCH64_CALL26;
#elif defined(TCC_TARGET_RISCV64)
	    if (!strcmp(reloc_name, "R_RISCV_CALL") || !strcmp(reloc_name, "R_RISCV_CALL_PLT"))
	        reloc_type = R_RISCV_CALL;
	    else if (!strcmp(reloc_name, "R_RISCV_BRANCH"))
	        reloc_type = R_RISCV_BRANCH;
	    else if (!strcmp(reloc_name, "R_RISCV_JAL"))
	        reloc_type = R_RISCV_JAL;
	    else if (!strcmp(reloc_name, "R_RISCV_PCREL_HI20"))
	        reloc_type = R_RISCV_PCREL_HI20;
	    else if (!strcmp(reloc_name, "R_RISCV_PCREL_LO12_I"))
	        reloc_type = R_RISCV_PCREL_LO12_I;
	    else if (!strcmp(reloc_name, "R_RISCV_PCREL_LO12_S"))
	        reloc_type = R_RISCV_PCREL_LO12_S;
	    else if (!strcmp(reloc_name, "R_RISCV_32_PCREL"))
	        reloc_type = R_RISCV_32_PCREL;
	    else if (!strcmp(reloc_name, "R_RISCV_32"))
	        reloc_type = R_RISCV_32;
	    else if (!strcmp(reloc_name, "R_RISCV_64"))
	        reloc_type = R_RISCV_64;
#endif
	    if (reloc_type < 0)
	        tcc_error("unimp: reloc '%s' unknown", reloc_name);
	    next();
	    skip(',');
	    greloca(cur_text_section, get_asm_sym(tok, NULL), e.v, reloc_type, 0);
	    next();
	}
	break;
    /* CFI directives: accepted, operands validated, data dropped (F9) */
    case TOK_ASMDIR_cfi_startproc:
        next();
        if (tok >= TOK_IDENT) {
            if (strcmp(get_tok_str(tok, NULL), "simple"))
                tcc_error("invalid .cfi_startproc operand '%s'",
                          get_tok_str(tok, NULL));
            next();
        }
        break;
    case TOK_ASMDIR_cfi_endproc:
    case TOK_ASMDIR_cfi_remember_state:
    case TOK_ASMDIR_cfi_restore_state:
    case TOK_ASMDIR_cfi_negate_ra_state:
        next();
        break;
    case TOK_ASMDIR_cfi_sections:
        next();
        for(;;) {
            if (tok == TOK_STR || tok >= TOK_IDENT)
                next();
            else
                tcc_error("section name expected in .cfi_sections");
            if (tok != ',')
                break;
            next();
        }
        break;
    case TOK_ASMDIR_cfi_def_cfa:
    case TOK_ASMDIR_cfi_offset:
    case TOK_ASMDIR_cfi_rel_offset:
        next();
        asm_cfi_reg(s1);
        skip(',');
        asm_int_expr(s1);
        break;
    case TOK_ASMDIR_cfi_register:
        next();
        asm_cfi_reg(s1);
        skip(',');
        asm_cfi_reg(s1);
        break;
    case TOK_ASMDIR_cfi_def_cfa_register:
    case TOK_ASMDIR_cfi_restore:
    case TOK_ASMDIR_cfi_undefined:
    case TOK_ASMDIR_cfi_same_value:
    case TOK_ASMDIR_cfi_return_column:
        next();
        asm_cfi_reg(s1);
        break;
    case TOK_ASMDIR_cfi_def_cfa_offset:
    case TOK_ASMDIR_cfi_adjust_cfa_offset:
        next();
        asm_int_expr(s1);
        break;
    case TOK_ASMDIR_cfi_personality:
    case TOK_ASMDIR_cfi_lsda:
        next();
        asm_int_expr(s1);
        skip(',');
        asm_cfi_name(s1);
        break;
    case TOK_ASMDIR_cfi_signal_frame:
        next();
        if (tok != ';' && tok != TOK_LINEFEED && tok != TOK_EOF)
            asm_cfi_reg(s1);
        break;
    case TOK_ASMDIR_cfi_escape:
        next();
        for(;;) {
            n = asm_int_expr(s1);
            if (n < 0 || n > 255)
                tcc_error(".cfi_escape operand %d out of byte range", n);
            if (tok != ',')
                break;
            next();
        }
        break;
    case TOK_ASMDIR_cfi_label:
        next();
        asm_cfi_name(s1);
        break;
    default:
        tcc_error("unknown assembler directive '.%s'", get_tok_str(tok, NULL));
        break;
    }
}


/* assemble a file */
static int tcc_assemble_internal(TCCState *s1, int do_preprocess, int global)
{
    int opcode;
    int saved_parse_flags = parse_flags;

    parse_flags = PARSE_FLAG_ASM_FILE | PARSE_FLAG_TOK_STR;
    if (do_preprocess)
        parse_flags |= PARSE_FLAG_PREPROCESS;
    asm_label_diffs_reset();
    asm_comm_reset();
    for(;;) {
        next();
        if (tok == TOK_EOF)
            break;
        tcc_debug_line(s1);
        parse_flags |= PARSE_FLAG_LINEFEED; /* XXX: suppress that hack */
    redo:
#if !defined(TCC_TARGET_ARM64)
        if (tok == '#') {
            /* horrible gas comment */
            while (tok != TOK_LINEFEED)
                next();
        } else
#endif
        if (tok >= TOK_ASMDIR_FIRST && tok <= TOK_ASMDIR_LAST) {
            asm_parse_directive(s1, global);
        } else if (tok == TOK_PPNUM) {
            const char *p;
            int n;
            p = tokc.str.data;
            n = strtoul(p, (char **)&p, 10);
            if (*p != '\0')
                expect("':'");
            /* new local label */
            asm_new_label(s1, asm_get_local_label_name(s1, n), 1);
            next();
            skip(':');
            goto redo;
        } else if (tok >= TOK_IDENT) {
            /* instruction or label */
            opcode = tok;
            next();
            if (tok == ':') {
                /* new label */
                asm_new_label(s1, opcode, 0);
                next();
                goto redo;
            } else if (tok == '=') {
		set_symbol(s1, opcode);
                goto redo;
            } else {
                asm_opcode(s1, opcode);
            }
        }
        /* end of line */
        if (tok != ';' && tok != TOK_LINEFEED)
            expect("end of line");
        parse_flags &= ~PARSE_FLAG_LINEFEED; /* XXX: suppress that hack */
    }

    asm_label_diffs_apply();
    asm_label_diffs_reset();
    asm_comms_apply(s1);
    asm_comm_reset();
    parse_flags = saved_parse_flags;
    return 0;
}

/* Assemble the current file */
ST_FUNC int tcc_assemble(TCCState *s1, int do_preprocess)
{
    int ret;
    tcc_debug_start(s1);
    /* default section is text */
    cur_text_section = text_section;
    ind = cur_text_section->data_offset;
    nocode_wanted = 0;
    ret = tcc_assemble_internal(s1, do_preprocess, 1);
    cur_text_section->data_offset = ind;
    tcc_debug_end(s1);
    return ret;
}

/********************************************************************/
/* GCC inline asm support */

/* assemble the string 'str' in the current C compilation unit without
   C preprocessing. */
static void tcc_assemble_inline(TCCState *s1, const char *str, int len, int global)
{
    const int *saved_macro_ptr = macro_ptr;
    int dotid = set_idnum('.', IS_ID);
#if !defined(TCC_TARGET_RISCV64) && !defined(TCC_TARGET_X86_64)
    int dolid = set_idnum('$', 0);
#endif

    tcc_open_bf(s1, ":asm:", len);
    memcpy(file->buffer, str, len);
    macro_ptr = NULL;
    tcc_assemble_internal(s1, 0, global);
    tcc_close();

#if !defined(TCC_TARGET_RISCV64) && !defined(TCC_TARGET_X86_64)
    set_idnum('$', dolid);
#endif
    set_idnum('.', dotid);
    macro_ptr = saved_macro_ptr;
}

/* find a constraint by its number or id (gcc 3 extended
   syntax). return -1 if not found. Return in *pp in char after the
   constraint */
ST_FUNC int find_constraint(ASMOperand *operands, int nb_operands, 
                           const char *name, const char **pp)
{
    int index;
    TokenSym *ts;
    const char *p;

    if (isnum(*name)) {
        index = 0;
        while (isnum(*name)) {
            index = (index * 10) + (*name) - '0';
            name++;
        }
        if ((unsigned)index >= nb_operands)
            index = -1;
    } else if (*name == '[') {
        name++;
        p = strchr(name, ']');
        if (p) {
            ts = tok_alloc(name, p - name);
            for(index = 0; index < nb_operands; index++) {
                if (operands[index].id == ts->tok)
                    goto found;
            }
            index = -1;
        found:
            name = p + 1;
        } else {
            index = -1;
        }
    } else {
        index = -1;
    }
    if (pp)
        *pp = name;
    return index;
}

static void subst_asm_operands(ASMOperand *operands, int nb_operands, 
                               CString *out_str, const char *str)
{
    int c, index, modifier;
    ASMOperand *op;
    SValue sv;

    for(;;) {
        c = *str++;
        if (c == '%') {
            if (*str == '%') {
                str++;
                goto add_char;
            }
            modifier = 0;
            if (*str == 'c' || *str == 'n' ||
                *str == 'b' || *str == 'w' || *str == 'h' || *str == 'k' ||
		*str == 'q' || *str == 'l' ||
#ifdef TCC_TARGET_ARM64
                *str == 'x' || *str == 's' || *str == 'd' || *str == 'Z' ||
#endif
#ifdef TCC_TARGET_RISCV64
		*str == 'z' ||
#endif
		/* P in GCC would add "@PLT" to symbol refs in PIC mode,
		   and make literal operands not be decorated with '$'.  */
		*str == 'P')
                modifier = *str++;
            index = find_constraint(operands, nb_operands, str, &str);
            if (index < 0)
        error:
                tcc_error("invalid operand reference after %%");
            op = &operands[index];
            if (modifier == 'l') {
                cstr_cat(out_str, get_tok_str(op->is_label, NULL), -1);
            } else {
		if (op->vt == NULL)
		    goto error;
                sv = *op->vt;
                if (op->reg >= 0) {
                    sv.r = op->reg;
                    if (op->is_memory)
                      sv.r |= VT_LVAL;
                }
                subst_asm_operand(out_str, &sv, modifier);
            }
        } else {
        add_char:
            cstr_ccat(out_str, c);
            if (c == '\0')
                break;
        }
    }
}


static void parse_asm_operands(ASMOperand *operands, int *nb_operands_ptr,
                               int is_output)
{
    ASMOperand *op;
    int nb_operands;
    char* astr;

    if (tok != ':') {
        nb_operands = *nb_operands_ptr;
        for(;;) {
            if (nb_operands >= MAX_ASM_OPERANDS)
                tcc_error("too many asm operands");
            op = &operands[nb_operands++];
            op->id = 0;
            if (tok == '[') {
                next();
                if (tok < TOK_IDENT)
                    expect("identifier");
                op->id = tok;
                next();
                skip(']');
            }
	    astr = parse_mult_str("string constant")->data;
            pstrcpy(op->constraint, sizeof op->constraint, astr);
            skip('(');
            gexpr();
            if (is_output) {
                if (!(vtop->type.t & VT_ARRAY))
                    test_lvalue();
            } else {
                /* we want to avoid LLOCAL case, except when the 'm'
                   constraint is used. Note that it may come from
                   register storage, so we need to convert (reg)
                   case */
                if ((vtop->r & VT_LVAL) &&
                    ((vtop->r & VT_VALMASK) == VT_LLOCAL ||
                     (vtop->r & VT_VALMASK) < VT_CONST) &&
                    !strchr(op->constraint, 'm')
#ifdef TCC_TARGET_ARM64
                    && !strchr(op->constraint, 'Q')
                    && !strstr(op->constraint, "Ump")
#endif
                    ) {
                    gv(RC_INT);
                }
            }
            op->vt = vtop;
            skip(')');
            if (tok == ',') {
                next();
            } else {
                break;
            }
        }
        *nb_operands_ptr = nb_operands;
    }
}

/* parse the GCC asm() instruction */
ST_FUNC void asm_instr(void)
{
    CString astr, *astr1;

    ASMOperand operands[MAX_ASM_OPERANDS];
    int nb_outputs, nb_operands, i, must_subst, out_reg, nb_labels;
    uint8_t clobber_regs[NB_ASM_REGS];
    Section *sec;

    /* since we always generate the asm() instruction, we can ignore
       volatile */
    while (tok == TOK_VOLATILE1 || tok == TOK_VOLATILE2 || tok == TOK_VOLATILE3
           || tok == TOK_GOTO) {
        next();
    }

    astr1 = parse_asm_str();
    cstr_new_s(&astr);
    cstr_cat(&astr, astr1->data, astr1->size);

    nb_operands = 0;
    nb_outputs = 0;
    nb_labels = 0;
    must_subst = 0;
    memset(clobber_regs, 0, sizeof(clobber_regs));
    if (tok == ':') {
        next();
        must_subst = 1;
        /* output args */
        parse_asm_operands(operands, &nb_operands, 1);
        nb_outputs = nb_operands;
        if (tok == ':') {
            next();
            if (tok != ')') {
                /* input args */
                parse_asm_operands(operands, &nb_operands, 0);
                if (tok == ':') {
                    /* clobber list */
                    next();
                    for(;;) {
                        if (tok == ':')
                          break;
                        if (tok != TOK_STR)
                            expect("string constant");
                        /* adjacent string literals concatenate
                           (e.g. "%"FF_REG_a in FFmpeg) */
                        {
                            CString clobstr;
                            cstr_new(&clobstr);
                            while (tok == TOK_STR) {
                                cstr_cat(&clobstr, tokc.str.data,
                                         tokc.str.size - 1);
                                next();
                            }
                            cstr_ccat(&clobstr, '\0');
                            asm_clobber(clobber_regs, clobstr.data);
                            cstr_free(&clobstr);
                        }
                        if (tok == ',') {
                            next();
                        } else {
                            break;
                        }
                    }
                }
                if (tok == ':') {
                    /* goto labels */
                    next();
                    for (;;) {
                        Sym *csym;
                        int asmname;
                        if (nb_operands + nb_labels >= MAX_ASM_OPERANDS)
                          tcc_error("too many asm operands");
                        if (tok < TOK_UIDENT)
                          expect("label identifier");
			memset(operands + nb_operands + nb_labels, 0,
			       sizeof(operands[0]));
                        operands[nb_operands + nb_labels++].id = tok;

                        csym = label_find(tok);
                        if (!csym) {
                            csym = label_push(&global_label_stack, tok,
                                              LABEL_FORWARD);
                        } else {
                            if (csym->r == LABEL_DECLARED)
                              csym->r = LABEL_FORWARD;
                        }
                        next();
                        asmname = asm_get_prefix_name(tcc_state, "LG.",
                                                      ++asmgoto_n);
                        if (!csym->c)
                          put_extern_sym2(csym, SHN_UNDEF, 0, 0, 1);
                        get_asm_sym(asmname, csym);
                        operands[nb_operands + nb_labels - 1].is_label = asmname;

                        if (tok != ',')
                          break;
                        next();
                    }
                }
            }
        }
    }
    skip(')');
    /* NOTE: we do not eat the ';' so that we can restore the current
       token after the assembler parsing */
    if (tok != ';')
        expect("';'");
    
    /* save all values in the memory */
    save_regs(0);

    /* compute constraints */
    asm_compute_constraints(operands, nb_operands, nb_outputs, 
                            clobber_regs, &out_reg);

    /* substitute the operands in the asm string. No substitution is
       done if no operands (GCC behaviour) */
#ifdef ASM_DEBUG
    printf("asm: \"%s\"\n", (char *)astr.data);
#endif
    if (must_subst) {
        cstr_reset(astr1);
        cstr_cat(astr1, astr.data, astr.size);
        cstr_reset(&astr);
        subst_asm_operands(operands, nb_operands + nb_labels, &astr, astr1->data);
    }

#ifdef ASM_DEBUG
    printf("subst_asm: \"%s\"\n", (char *)astr.data);
#endif

    /* generate loads */
    asm_gen_code(operands, nb_operands, nb_outputs, 0, 
                 clobber_regs, out_reg);    

    /* We don't allow switching section within inline asm to
       bleed out to surrounding code.  */
    sec = cur_text_section;
    /* assemble the string with tcc internal assembler */
    tcc_assemble_inline(tcc_state, astr.data, astr.size - 1, 0);
    cstr_free_s(&astr);
    if (sec != cur_text_section) {
        tcc_warning("inline asm tries to change current section");
        use_section1(tcc_state, sec);
    }

    /* restore the current C token */
    next();

    /* store the output values if needed */
    asm_gen_code(operands, nb_operands, nb_outputs, 1, 
                 clobber_regs, out_reg);
    
    /* free everything */
    for(i=0;i<nb_operands;i++) {
        vpop();
    }

}

ST_FUNC void asm_global_instr(void)
{
    CString *astr;
    int saved_nocode_wanted = nocode_wanted;

    /* Global asm blocks are always emitted.  */
    nocode_wanted = 0;
    next();
    astr = parse_asm_str();
    skip(')');
    /* NOTE: we do not eat the ';' so that we can restore the current
       token after the assembler parsing */
    if (tok != ';')
        expect("';'");
    
#ifdef ASM_DEBUG
    printf("asm_global: \"%s\"\n", (char *)astr->data);
#endif
    cur_text_section = text_section;
    ind = cur_text_section->data_offset;

    /* assemble the string with tcc internal assembler */
    tcc_assemble_inline(tcc_state, astr->data, astr->size - 1, 1);
    
    cur_text_section->data_offset = ind;

    /* restore the current C token */
    next();

    nocode_wanted = saved_nocode_wanted;
}

/********************************************************/
#else
ST_FUNC int tcc_assemble(TCCState *s1, int do_preprocess)
{
    tcc_error("asm not supported");
}

ST_FUNC void asm_instr(void)
{
    tcc_error("inline asm() not supported");
}

ST_FUNC void asm_global_instr(void)
{
    tcc_error("inline asm() not supported");
}
#endif /* CONFIG_TCC_ASM */
