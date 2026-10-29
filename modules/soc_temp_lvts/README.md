# soc_temp_lvts.ko source for emerald

MediaTek LVTS thermal driver (the CPU / GPU / SoC sensors of mt6789), built out of tree for the stock GKI
kernel in this repo (6.12.30, ci.android.com build 13847919, kernel/common 6e872b4863d6). The build ships
it as `vendor_dlkm/soc_temp_lvts.ko` (see the top-level README).

| File | Source |
|---|---|
| `soc_temp_lvts.c`, `soc_temp_lvts.h` | [oppo-source/android_kernel_modules_and_devicetree_oppo_mt6993](https://github.com/oppo-source/android_kernel_modules_and_devicetree_oppo_mt6993) 4d505a4292dab3176a45fec66dc85debc362e24c, `kernel/kernel_device_modules-6.12/drivers/thermal/mediatek/` (MediaTek, GPL-2.0). Closest of four candidate trees to the stock OS3.0.305.0 module: 89 of its 92 strings, the 3 missing are Xiaomi debug prints |
| `thermal_interface.h` | [zhaoqing412/android_kernel_modules_xiaomi_mt6895-6.12](https://github.com/zhaoqing412/android_kernel_modules_xiaomi_mt6895-6.12) 7c3d5677804b46fda6838537f95bf3ce2d5953ad, `kernel_device_modules-6.12/drivers/thermal/mediatek/` |
| `mtk-include/linux/soc/mediatek/mtk_sip_svc.h` | same tree, `kernel_device_modules-6.12/include/linux/soc/mediatek/`. Force-included by Kbuild: it has the same include guard as the GKI header, which lacks `MTK_SIP_KERNEL_THROTTLE_CONTROL` |
| `Module.symvers.ti` | CRCs of the four `thermal_interface` exports as the stock module imports them (`ko_versions.py`) |
| `Kbuild`, `ko_versions.py`, `cfi_hashes.py` | ours |

## Build

1. Kernel tree: `kernel/common` at 6e872b4863d6dd892490c32d973db1a9df8d3710. `.config` = the phone's
   `/proc/config.gz`, then `make olddefconfig modules_prepare` with `ARCH=arm64 LLVM=1`, clang r547379 and
   pahole (`prebuilts/kernel-build-tools/linux-x86/bin`) in `PATH`. Without pahole BTF is turned off and
   `struct module` changes layout; without rustc a `gki_defconfig` build drops
   `CONFIG_CFI_ICALL_NORMALIZE_INTEGERS` and every kCFI type hash differs. An empty
   `protected_module_names_list` keeps modpost quiet.
2. `Module.symvers.all` = `vmlinux.symvers` from ci.android.com build 13847919 (`kernel_aarch64`) +
   `Module.symvers.ti`. Never use CRCs computed locally: gendwarfksyms with a newer clang does not match the
   running kernel.
3. Build:

       make -C <out> ARCH=arm64 LLVM=1 M=$PWD KBUILD_EXTRA_SYMBOLS=$PWD/Module.symvers.all modules

## Checks before loading it on the phone

A wrong kCFI hash panics the kernel on `insmod`, so compare with the stock module first:

- `ko_versions.py <llvm-objcopy> <ko>`: the CRC of every import equals the stock module's; new imports
  come from the official `vmlinux.symvers`.
- `cfi_hashes.py <llvm-readelf> <ko>`: the type hashes of the functions both modules have are equal;
  `init_module` is `0x6fbb3035`.
- `.gnu.linkonce.this_module`: size 0x640, `init_module` relocation at 0x188 and `cleanup_module` at
  0x5f8, as in the stock module.

## Changes against the imported source

**Re-initialize LVTS on resume.** LVTS loses power in s2idle, and the stock module has empty suspend/resume
callbacks, so after the first sleep every LVTS thermal zone (CPU, GPU, SoC) reads invalid until a reboot. The
5.10 driver for the same chip (MotorolaMobilityLLC/kernel-mtk 4cbe43fe20dc, branch android-13-release-ttt)
stops the sensors on suspend (`lvts_close`) and runs `lvts_init` on resume. We do the same with the 6.12 ops,
except that suspend only stops sensing: unlike `lvts_close` it neither closes the devices nor turns `lvts_clk`
off; the clock reference taken at probe is held until remove.

- `suspend_noirq` stops sensing; `resume_noirq` resets the controllers and re-runs device identification,
  enable/init, RC count, calibration, controller init, enables sensing and arms the hardware reboot.
- Calibration: LK programs the efuse calibration and the 6.12 driver keeps no copy, so probe saves what LK
  wrote (EDATA registers) and resume writes it back. If a sensor has none, RC is measured as usual.
- Clock: the driver only looks up `lvts_clk`, which LK leaves on; probe now holds a reference so it stays on.
- Hardware over-temperature reboot: resume arms it at 113.5 C, as the 5.10 driver did. Stock LK leaves it off
  (PROTTC 0) and the 6.12 driver arms it only from `set_trip_temp`; keeping it on is the user's decision.
- Root-only parameter `reinit` (write 1) re-runs the init by hand and logs the calibration registers before and
  after.
- Remove drops the clock reference and clears the `reinit` target (under the module's parameter lock), so that
  the module can be unloaded and loaded again.

Tested on the phone 2026-10-19 (module sha256 81f680cf..., loaded with rmmod/insmod, the stock module stays in
vendor_dlkm): 12 suspends, all LVTS zones live after each, the LK calibration identical after every resume.
With the remove fix (2026-10-20, module sha256 acb68959..., stripped with `llvm-strip --strip-debug`): one
unload/load cycle of the new remove (lvts_clk enable count 3 -> 2 -> 3), reinit, then suspends with the LK
calibration restored on every resume.
