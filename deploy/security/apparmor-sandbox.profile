# AppArmor profile for SuperAgente IA code execution sandbox
# Install: sudo apparmor_parser -r -W deploy/security/apparmor-sandbox.profile

#include <tunables/global>

profile superagente-sandbox flags=(attach_disconnected,mediate_deleted) {
  #include <abstractions/base>

  # Deny all network access
  deny network,

  # Deny all mount operations
  deny mount,
  deny umount,
  deny pivot_root,

  # Deny ptrace (anti-debugging/escape)
  deny ptrace,

  # Deny raw socket access
  deny network raw,
  deny network packet,

  # Deny access to sensitive proc entries
  deny /proc/*/mem rw,
  deny /proc/*/maps r,
  deny /proc/sysrq-trigger rw,
  deny /proc/kcore r,
  deny /proc/kallsyms r,
  deny /sys/** w,

  # Deny device access
  deny /dev/** rw,
  # Allow null, zero, urandom, random
  /dev/null rw,
  /dev/zero r,
  /dev/urandom r,
  /dev/random r,

  # Python execution (read-only)
  /usr/local/bin/python3* ix,
  /usr/local/lib/python3*/** r,
  /usr/lib/python3*/** r,

  # Workspace (read-only)
  /workspace/** r,

  # Temp directory (read-write, limited)
  /tmp/** rw,
  deny /tmp/** x,

  # Deny access to host filesystem
  deny /home/** rw,
  deny /root/** rw,
  deny /etc/shadow r,
  deny /etc/passwd w,
  deny /etc/gshadow r,

  # Deny capability escalation
  deny capability sys_admin,
  deny capability sys_ptrace,
  deny capability sys_rawio,
  deny capability sys_module,
  deny capability net_admin,
  deny capability net_raw,
  deny capability mknod,
  deny capability audit_write,
  deny capability dac_override,
  deny capability fowner,
  deny capability fsetid,
  deny capability setuid,
  deny capability setgid,
  deny capability setpcap,
}
