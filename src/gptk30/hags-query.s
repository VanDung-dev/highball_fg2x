# Compatibility response for Wine's Unix (System V x86_64) entry point.
# This reports MetalFX FG compatibility; it does not implement Windows HAGS.
.text
.globl _fg2x_query
_fg2x_query:
    testq %rdi, %rdi
    jz Linvalid
    cmpl $70, 4(%rdi)
    jne Lunsupported
    cmpl $0, (%rdi)
    je Linvalid
    cmpl $4, 16(%rdi)
    jb Linvalid
    movq 8(%rdi), %rax
    testq %rax, %rax
    jz Linvalid
    movl $7, (%rax)
    xorl %eax, %eax
    retq
Lunsupported:
    movl $0xc0000002, %eax
    retq
Linvalid:
    movl $0xc000000d, %eax
    retq
