# OneThreeOctave-SVG-Compare

1/3 倍频程对比（项目名称）。当前初始版本为 **Three.js + Python Bokeh** 的三维选点联动数据分析 Demo。

## 快速运行

```bash
python -m pip install -r requirements.txt
python main.py
```

浏览器打开 `http://127.0.0.1:8080/viewer/index.html`。服务只监听 `127.0.0.1`。设置 `PORT=8081` 可修改端口；设置 `NO_BROWSER=1` 可跳过自动打开浏览器。

- 左侧 Three.js 显示可拾取的演示柱体 `C001` / `C002` / `C003`，支持轨道旋转、缩放、平移。
- 点击柱体后，通过 `postMessage` 通知右侧 Bokeh iframe；`ColumnDataSource` 将选择同步给 Python 后端，更新温度历史曲线，不会刷新页面。
- 演示数据定义于 `main.py` 的 `SENSORS` 和 `query_sensor_history`；替换为真实数据查询即可。
- 可将你的 GLB 放在 `frontend/assets/柱子.glb`；需保证不同 Mesh 对应可识别的 `elementId` 或名称。
- 目前图纸平面是示例几何体。精确 Fab / Subfab SVG 绘制还需集成原有的 SVG 纹理函数；该 Demo **不包含**原始图纸和 GLB。
- Three.js 仍通过 unpkg CDN 加载，浏览器第一次加载需要网络连接。

## 双轨测试

本地与 GitHub Actions 都使用 **同一组 unittest**：

```bash
python tests/run_tests.py
```

运行后生成或更新根目录的 `test_report.md`，即使测试失败也记录 FAIL 和错误详情。`.github/workflows/test.yml` 在 `main` 推送、PR 和手动触发时运行测试，始终上传报告产物，并在 main 推送事件下将报告写回仓库。仅修改 `test_report.md` 的推送不会引发 CI 循环。

测试包括 Bokeh 选择回调、传感器数据、前端通信约定以及真实 Bokeh HTTP 服务。**WebGL 画面仍需人工视觉测试**，不属于单元测试通过的结论。

## 安全边界

这是仅供本地使用的 Demo。正式向外提供服务前需增加身份验证、授权、请求校验与访问控制。
