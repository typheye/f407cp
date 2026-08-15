#ifndef TOS_LIBEHW_H
#define TOS_LIBEHW_H

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
  EHW_EXPR_NONE = 0,
  EHW_EXPR_DIZZY,
  EHW_EXPR_PETTED,
  EHW_EXPR_COLD,
  EHW_EXPR_COMFY,
  EHW_EXPR_HOT,
  EHW_EXPR_DARK,
  EHW_EXPR_BRIGHT,
} EHW_Expr_t;

void EHW_Init(void);
EHW_Expr_t EHW_Update(void);
EHW_Expr_t EHW_GetExpr(void);

#ifdef __cplusplus
}
#endif

#endif
