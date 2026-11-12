# CfdOF macOS 使用说明

Justin Wang 贡献了 macOS 移植，并非 CfdOF 的第一作者。此分支保留了 [上游 CfdOF](https://github.com/jaheyns/CfdOF) 的提交历史、原作者署名和 LGPL-3.0-or-later 许可证。详见[移植和署名说明](../PORTING.md)。

## 在已安装的 Mac 上使用

打开 FreeCAD 1.1.4，选择 **CfdOF** 工作台。在 **CfdOF → Open preferences** 运行依赖检查。实测 Apple Silicon 环境识别了 OpenFOAM v2406、cfMesh-CfdOF 1.33、HiSA 1.13.4、ParaView 5.12.1 和 FreeCAD 自带的 Gmsh 4.15.0。

三种网格工具 cfMesh、snappyHexMesh 和 Gmsh 均通过网格检查。cfMesh 和 HiSA 的单进程及双进程流程均已实测，并行结果可用 `reconstructPar` 重构。ParaView 能读取 HiSA 的速度、压力、温度和马赫数结果。

HiSA 的可压缩算例可参照上游示例，在初始场设置中直接指定流场或从边界取值。对采用特征边界的测试算例，`potentialFoam` 初始化不适用。Intel Mac 和其他 OpenFOAM 版本尚未验证。

## 在另一台 Apple Silicon Mac 上安装

先安装 [FreeCAD](https://www.freecad.org/downloads/)、[OpenFOAM-v2406.app](https://github.com/gerlero/openfoam-app) 和 [ParaView](https://www.paraview.org/download/)。编译 cfMesh 和 HiSA 需要 Xcode 或 Xcode Command Line Tools。关掉 FreeCAD，在解压后的 `CfdOF` 目录运行：

```sh
/bin/bash macos/install.command
/bin/bash macos/install-dependencies.command
```

第一个脚本安装工作台。第二个脚本校验上游源码归档，编译 cfMesh 和 HiSA，并将产物装入 OpenFOAM 的用户目录。已有同名文件会备份。把算例和 OpenFOAM 用户目录放在可写、不含空格的路径下。

重启 FreeCAD，选择 **CfdOF**，运行依赖检查。如果未自动发现 OpenFOAM，可在设置中填写整个 `.app` 的路径。脚本选项可用 `/bin/bash macos/install-dependencies.command --help` 查看。
