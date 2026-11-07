#ifndef _FLOAT_H_
#define _FLOAT_H_

#define FLT_RADIX 2

/* Evaluation method of expressions involving float/double (C11
   5.2.4.2.2).  x86-64 evaluates in SSE registers, each type in its
   own format: 0.  i386 evaluates on the x87 stack (fld/fmul/fadd on
   80-bit operands), so float and double are evaluated in the format
   of long double: 2.  The remaining backends (ARM, AArch64, RISC-V,
   C67) execute each floating-point operation in the operand type's
   own format: 0.  Verified against the generated code for x86-64
   (SSE mulsd/addsd/mulss) and i386 (x87 fldl/fmull/faddl). */
#if defined __i386__
#define FLT_EVAL_METHOD 2
#else
#define FLT_EVAL_METHOD 0
#endif

/* Every floating-point format this header describes is an IEC 60559
   format and supports subnormal (denormal) numbers (C11). */
#define FLT_HAS_SUBNORM 1
#define DBL_HAS_SUBNORM 1
#define LDBL_HAS_SUBNORM 1

/* IEEE float */
#define FLT_MANT_DIG 24
#define FLT_DIG 6
#define FLT_DECIMAL_DIG 9
#define FLT_ROUNDS 1
#define FLT_EPSILON 1.19209290e-07F
#define FLT_MIN_EXP (-125)
#define FLT_MIN 1.17549435e-38F
#define FLT_TRUE_MIN 1.40129846432481707092372958328991613e-45F
#define FLT_MIN_10_EXP (-37)
#define FLT_MAX_EXP 128
#define FLT_MAX 3.40282347e+38F
#define FLT_MAX_10_EXP 38

/* IEEE double */
#define DBL_MANT_DIG 53
#define DBL_DIG 15
#define DBL_DECIMAL_DIG 17
#define DBL_EPSILON 2.2204460492503131e-16
#define DBL_MIN_EXP (-1021)
#define DBL_MIN 2.2250738585072014e-308
#define DBL_TRUE_MIN 4.94065645841246544176568792868221372e-324
#define DBL_MIN_10_EXP (-307)
#define DBL_MAX_EXP 1024
#define DBL_MAX 1.7976931348623157e+308
#define DBL_MAX_10_EXP 308

/* horrible intel long double */
#if defined __i386__ || defined __x86_64__

#define LDBL_MANT_DIG 64
#define LDBL_DIG 18
#define LDBL_DECIMAL_DIG 21
#define LDBL_EPSILON 1.08420217248550443401e-19L
#define LDBL_MIN_EXP (-16381)
#define LDBL_MIN 3.36210314311209350626e-4932L
#define LDBL_TRUE_MIN 3.64519953188247460252840593361941982e-4951L
#define LDBL_MIN_10_EXP (-4931)
#define LDBL_MAX_EXP 16384
#define LDBL_MAX 1.18973149535723176502e+4932L
#define LDBL_MAX_10_EXP 4932
#define DECIMAL_DIG 21

#elif defined __aarch64__ || defined __riscv
/*
 * Use values from:
 * gcc -dM -E -xc /dev/null | grep LDBL | sed -e "s/__//g"
 */
#define LDBL_MANT_DIG 113
#define LDBL_DIG 33
#define LDBL_DECIMAL_DIG 36
#define LDBL_EPSILON 1.92592994438723585305597794258492732e-34L
#define LDBL_MIN_EXP (-16381)
#define LDBL_MIN 3.36210314311209350626267781732175260e-4932L
#define LDBL_TRUE_MIN 6.47517511943802511092443895822764655e-4966L
#define LDBL_MIN_10_EXP (-4931)
#define LDBL_MAX_EXP 16384
#define LDBL_MAX 1.18973149535723176508575932662800702e+4932L
#define LDBL_MAX_10_EXP 4932
#define DECIMAL_DIG 36

#else

/* same as IEEE double */
#define LDBL_MANT_DIG 53
#define LDBL_DIG 15
#define LDBL_DECIMAL_DIG 17
#define LDBL_EPSILON 2.2204460492503131e-16L
#define LDBL_MIN_EXP (-1021)
#define LDBL_MIN 2.2250738585072014e-308L
#define LDBL_TRUE_MIN 4.94065645841246544176568792868221372e-324L
#define LDBL_MIN_10_EXP (-307)
#define LDBL_MAX_EXP 1024
#define LDBL_MAX 1.7976931348623157e+308L
#define LDBL_MAX_10_EXP 308
#define DECIMAL_DIG 17

#endif

#endif /* _FLOAT_H_ */
