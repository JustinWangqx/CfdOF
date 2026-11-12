# CfdOF macOS port / CfdOF macOS 移植

## Credits / 署名

Justin Wang contributed the macOS port. He is not the original author of
CfdOF. This fork is based on [jaheyns/CfdOF](https://github.com/jaheyns/CfdOF)
at [`fcc3766`](https://github.com/jaheyns/CfdOF/commit/fcc3766059118fd893b1a99fa61e0b2a3326003a).
The earliest inherited commit, [`c100a75`](https://github.com/jaheyns/CfdOF/commit/c100a75),
is by Qingfeng Xia (`qingfengxia`). Oliver Oxtoby is listed as maintainer in
the upstream package metadata. See the [upstream acknowledgements](README.md#acknowledgements)
for the other contributors.

Justin Wang 贡献了 macOS 移植，并非 CfdOF 第一作者。此分支基于上游
`jaheyns/CfdOF` 的 `fcc3766` 提交，保留了上游历史。最早继承的提交
`c100a75` 由 Qingfeng Xia（`qingfengxia`）提交，上游包元数据列出的维护者是
Oliver Oxtoby。其他贡献者见 [README 的致谢](README.md#acknowledgements)。

CfdOF remains under [LGPL-3.0-or-later](LICENSE). Original copyright and
license notices remain in place. The dependency installer retrieves cfMesh-CfdOF
and HiSA from their own upstream projects under their respective licenses.

CfdOF 沿用 [LGPL-3.0-or-later](LICENSE)，原有版权和许可证声明完整保留。
依赖安装脚本从各自上游获取 cfMesh-CfdOF 和 HiSA，两者分别遵循各自的许可证。

## Setup / 安装

The tested configuration uses an Apple Silicon Mac, FreeCAD 1.1.4,
OpenFOAM-v2406.app, and ParaView 5.12.1. Gmsh 4.15.0 came with this FreeCAD
build. Install the arm64 applications from
[FreeCAD](https://www.freecad.org/downloads/),
[OpenFOAM.app](https://github.com/gerlero/openfoam-app), and
[ParaView](https://www.paraview.org/download/).
Building cfMesh-CfdOF and HiSA also requires the Xcode Command Line Tools.

实测环境为 Apple Silicon Mac、FreeCAD 1.1.4、OpenFOAM-v2406.app 和
ParaView 5.12.1。该 FreeCAD 版本内附 Gmsh 4.15.0。请从上述链接安装 arm64
版本。编译 cfMesh-CfdOF 和 HiSA 还需要 Xcode Command Line Tools。

From the root of this checkout or an extracted source archive, run the
installers below. The second script builds both native dependencies in the
OpenFOAM.app environment and installs them to OpenFOAM's user directories.

在源码仓库根目录或解压后的源码目录中运行以下命令。第二个脚本使用
OpenFOAM.app 环境编译两个原生依赖，并安装到 OpenFOAM 的用户目录。

```sh
/bin/bash macos/install.command
/bin/bash macos/install-dependencies.command
```

Restart FreeCAD, select **CfdOF**, and run the dependency check under
**CfdOF → Open preferences**. If automatic discovery does not find OpenFOAM,
set the OpenFOAM path to the installed `.app` bundle.

重启 FreeCAD，选择 **CfdOF** 工作台，在 **CfdOF → Open preferences** 中运行
依赖检查。如果未自动找到 OpenFOAM，将 OpenFOAM 路径设为已安装的
`.app` 文件。

## Verification / 验证

- The native workbench loaded in FreeCAD. CfdOF generated snappyHexMesh and
  Gmsh meshes, and both passed `checkMesh`.
- The workflow ran a serial solve and a two-process MPI solve, reconstructed
  the parallel result, and read pressure and velocity fields in ParaView.
- cfMesh-CfdOF 1.33 and HiSA 1.13.4 were built for arm64 and identified by
  CfdOF's dependency checker. CfdOF generated a 4,624-cell cfMesh duct mesh
  that passed `checkMesh`, then ran the steady compressible HiSA case to
  iteration 25 and wrote velocity, pressure, temperature, and Mach number.
- cfMesh and HiSA also ran with two MPI processes. The 7,260-cell mesh
  passed `checkMesh`, and `reconstructPar` combined the fields at iteration 25.

Those checks cover the tested Apple Silicon configuration. Intel Macs and
other OpenFOAM versions have not been validated by this port.

- CfdOF 工作台在原生 FreeCAD 中加载，生成了 snappyHexMesh 和 Gmsh 网格，
  两种网格均通过 `checkMesh`。
- 流程验证了串行求解、双进程 MPI 求解和并行结果重构，并在 ParaView 中读取了
  压力场和速度场。
- cfMesh-CfdOF 1.33 和 HiSA 1.13.4 已编译为 arm64 版本，并由 CfdOF 的依赖
  检查识别。CfdOF 用 cfMesh 生成了 4,624 个单元的管道网格，通过
  `checkMesh`，并用 HiSA 将稳态可压缩流算例运行到第 25 次迭代，
  输出速度、压力、温度和马赫数。
- cfMesh 和 HiSA 均通过双进程 MPI 实测。包含 7,260 个单元的网格通过
  `checkMesh`，并成功重构第 25 次迭代的结果。

以上结果适用于实测的 Apple Silicon 环境。Intel Mac 和其他 OpenFOAM 版本
尚未验证。
