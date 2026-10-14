# BrandScope AI · 作品集演示版

消费者洞察与品牌营销机会分析平台。基于 Python、Streamlit、Pandas、Plotly、Pydantic 和 SQLite 构建。

## 演示范围

包含数据工作台、消费者洞察、竞品分析、营销机会雷达、AI 策略报告五个模块。内置 3,000 条固定随机种子生成的模拟咖啡评论，界面和报告均标注为模拟数据。演示标签不调用大模型 API。

## 在线发布

1. 将本目录内的文件上传到自己的 GitHub 仓库（例如 brandscope-ai）。注意保持 core、pages、models、services、data 等子目录结构。
2. 登录 https://share.streamlit.io/ ，连接该 GitHub 账号。
3. 点击 Create app，选择已有应用，填写仓库、分支 main，Main file path 填 app.py。
4. 在 Advanced settings 中选择 Python 3.12。演示版无需填写 Secrets。
5. 点击 Deploy。部署完成后，复制页面提供的实际公开网址。
6. 确认应用允许所有人访问，再用未登录浏览器或手机测试该网址，最后制作简历二维码。

不要把本地 localhost 地址写进简历二维码：它只指向扫码者自己的设备。

## 体验路径

打开网页 → 使用演示数据 → 确认数据集 → 生成演示标签 → 消费者洞察 / 竞品分析 / 营销机会雷达 → AI 策略报告 → 生成并保存策略报告。

## 本地启动

建议 Python 3.12。

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

发布包只含应用源码、依赖清单、样式配置及模拟数据。真实上传数据需配置模型服务后才能完成文本标注。云端本地 SQLite 保存不保证在重部署后保留。

官方部署说明：https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
