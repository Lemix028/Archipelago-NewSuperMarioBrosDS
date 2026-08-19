.syntax unified
.arm

.section .text
.align 2

.global nsmbds_ap_patch_marker_hook
.type nsmbds_ap_patch_marker_hook, %function
nsmbds_ap_patch_marker_hook:
    bx lr

.align 2
.global nsmbds_ap_patch_marker
.type nsmbds_ap_patch_marker, %object
nsmbds_ap_patch_marker:
    .ascii "APNS"
    .word 1
    .word 0
    .word 0

.size nsmbds_ap_patch_marker, . - nsmbds_ap_patch_marker
