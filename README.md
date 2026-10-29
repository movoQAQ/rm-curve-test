# RM Curve Test

RoboMaster 导航曲线路段测试的历史资料归档。保留原有二维地图、地图编辑与参数调节工具，以及共用导航参数的当前快照，方便以后查阅和恢复。

**当前已停止使用这段 S 弯，仓库以归档为目的。此次整理没有重新运行导航、仿真或实车测试。**

## 原来的用途

根据原使用者说明，S 弯是测试地图中的一段路线，沿用原导航工程的同一套参数，不是通过单独程序生成 S 弯速度指令。`cmd_vel_speed_test` 用于直线速度测试，不属于本次归档内容。

本次明确提供的地图文件名为 `ground.pgm`，因此保留原名及其配套 `ground.yaml`。早先提及的 `curvetest` 名称未对应到独立文件，本仓库没有据此生成或重命名地图，也没有补造 S 弯路径、起终点或测试结果。

## 归档内容

```text
rm-curve-test/
├── maps/
│   ├── ground.pgm
│   └── ground.yaml
├── config/
│   ├── nav2_params.snapshot.yaml
│   └── behavior_tree/
│       ├── navigate_to_pose_w_replanning_and_recovery.xml
│       └── navigate_through_poses_w_replanning_and_recovery.xml
├── src/
│   ├── map_edit/                     # ROS 2 RViz 地图编辑插件
│   └── control_server_param_ui/      # Python ROS 参数调节界面
├── archive_manifest.json             # 来源、文件映射和原文件 SHA-256
└── SHA256SUMS                        # 归档文件校验清单
```

### 地图

`maps/ground.pgm` 与原文件逐字节一致，未改动地图像素。地图尺寸为 **708 × 460 像素**，对应 YAML 中：

| 参数 | 值 |
|---|---|
| 分辨率 | 0.05 米/像素 |
| 原点 | `[-18.4, -9.53, 0]` |
| negate | 0 |
| occupied_thresh | 0.65 |
| free_thresh | 0.196 |

PGM 保存的是栅格地图，不是单独的路径轨迹文件；本次没有获得 S 弯对应的路径点序列或精确起终点标注。

### 地图编辑插件

`src/map_edit` 是 ROS 2 RViz 插件，支持加载地图、添加/擦除障碍、画直线、撤销和保存 PGM/YAML。编辑结果发布到 `/map_edit`，导航是否采用修改后的地图由外部系统配置决定。

源码来自 [Tony-tpc/map_edit](https://github.com/Tony-tpc/map_edit)，本次保存的是本地现状，包括 CMake、包声明、RViz 配置和橡皮擦实现中的已有修改。原说明保存在 `src/map_edit/readme.md`。

### 参数调节工具

`src/control_server_param_ui/control_server_param_ui.py` 使用 Python Tkinter 界面调用 `ros2 param list/get/set`，支持读取参数、单项修改和批量提交。

当前代码默认节点名是 `/controller_server`，可在界面中修改。子目录原 README 中的 `/control_server` 是旧说明，以源码默认值为准。

### 共用导航参数参考

`config/nav2_params.snapshot.yaml` 来自归档时的 2026 导航工程工作区，包含已有未提交修改。当前配置使用 `pb_omni_pid_pursuit_controller::OmniPidPursuitController` 控制器和 `nav2_navfn_planner::NavfnPlanner` 规划器。

**这是 2026-10-29 归档时的参考快照，不能证明它与历史 S 弯测试当时的参数完全一致。** 两份行为树 XML 一并保存，便于理解配置引用。

为避免公开本机目录，参数快照中的本机绝对路径已替换为仓库相对路径或 `reference_navigation/` 占位路径；没有修改原导航工程。普通 YAML 不会自动把所有相对路径解析成包路径，复用前应由启动配置显式解析这些路径。

## 日后恢复工具

以下仅说明原工具的恢复入口，不代表已验证完整的 S 弯复现流程。

在已经配置 ROS 2、colcon 及工具依赖的环境中，从仓库根目录构建地图编辑插件：

```bash
colcon build --symlink-install --packages-select map_edit
source install/setup.bash
ros2 launch map_edit mapeidt.launch.py
```

`mapeidt.launch.py` 是原有文件名，拼写保持不变。插件需要 RViz、Qt5、OpenCV、cv_bridge 及相关 ROS 消息和 TF 依赖。打开插件后，选择 `maps/ground.yaml` 加载归档地图。

参数界面在加载 ROS 环境、目标参数节点已运行且具备图形会话时启动：

```bash
python3 src/control_server_param_ui/control_server_param_ui.py
```

完整导航还需要外部的定位、TF、传感器数据、底盘接口和自定义导航插件。本仓库没有将整个导航工程搬入，也未提供一键跑通 S 弯的启动入口。

## 完整性与来源

- `archive_manifest.json` 记录原工作空间内的相对文件名、归档位置和 SHA-256，可核对地图和工具源码是否原样保存。
- 原工作空间中的地图与工具文件全部按当前内容保存，包含未提交源码修改；不保留嵌套 Git 元数据、Python 缓存、编译产物、安装产物和构建日志。
- 共用导航参数和行为树只复制为参考资料，原导航工程及直线速度测试包不属于本次清理范围。
- 文档和配置不包含原机器的用户目录绝对路径。

从仓库根目录检查归档文件：

```bash
sha256sum -c SHA256SUMS
```

本次检查范围为文件复制一致性、地图可读性、Python 语法、YAML/XML 可解析性与远端归档完整性。未进行 ROS 编译或运动测试。

## 许可证说明

保留各文件已有作者和来源信息。原 `map_edit` 包的许可证字段仍为 `TODO`；此次归档不替原作者指定新的许可证。
