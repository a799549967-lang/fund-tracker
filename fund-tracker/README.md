# 帅哥估值 - 基金持仓实时估值工具

GitHub Actions 自动抓取东方财富数据，无需任何服务器或代理。

## 部署步骤（5分钟）

### 第一步：创建 GitHub 仓库

1. 登录 GitHub，点右上角 **+** → **New repository**
2. 仓库名填 `fund-tracker`
3. 设为 **Public**（必须，否则 GitHub Pages 需要付费）
4. 点 **Create repository**

### 第二步：上传文件

把以下文件按目录结构上传到仓库：

```
fund-tracker/
├── .github/
│   └── workflows/
│       └── fetch.yml          ← 自动抓数据的 Actions
├── data/
│   ├── holdings.json          ← 你持有的基金列表
│   └── funds.json             ← 自动生成，不用改
├── scripts/
│   └── fetch_funds.py         ← 数据抓取脚本
└── index.html                 ← 主页面（从 public/index.html 复制过来）
```

> 上传方式：在仓库页面点 **Add file** → **Upload files**

### 第三步：开启 GitHub Pages

1. 仓库 → **Settings** → **Pages**
2. Source 选 **Deploy from a branch**
3. Branch 选 **main**，目录选 **/ (root)**
4. 点 **Save**

### 第四步：修改 index.html 里的配置

打开 `index.html`，找到这一行（大约在底部 script 开头）：

```javascript
var REPO_RAW = 'https://raw.githubusercontent.com/YOUR_USERNAME/fund-tracker/main';
```

把 `YOUR_USERNAME` 改成你的 GitHub 用户名，然后保存上传。

### 第五步：启用 Actions 权限

1. 仓库 → **Settings** → **Actions** → **General**
2. 找到 **Workflow permissions**
3. 选 **Read and write permissions**
4. 点 **Save**

---

## 使用方法

1. 打开 `https://你的用户名.github.io/fund-tracker/`
2. 点「添加」，输入基金代码
3. 添加后点「数据管理」→「同步到GitHub」，下载 `holdings.json`
4. 将 `holdings.json` 上传到仓库的 `data/` 目录，**覆盖**原有文件
5. GitHub Actions 会在交易日每 5 分钟自动抓取一次数据

## 数据更新频率

- 交易日 09:30–11:30、13:00–15:00：每 5 分钟
- 非交易时间：不更新

## 手动触发更新

仓库 → **Actions** → **Fetch Fund Data** → **Run workflow**
