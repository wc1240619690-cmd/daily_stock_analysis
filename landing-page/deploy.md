# Landing Page 部署指南

## 上线前配置

### 1. 替换占位符

在 `index.html` 中搜索并替换以下内容：

| 占位符 | 替换为 | 位置 |
|--------|--------|------|
| `your-form-id` | Formspree 表单 ID | form action |
| `your-wechat-id` | 你的微信号（共 2 处） | 表单成功提示 + 二维码区域 |

### 2. 配置表单收集（二选一）

#### 方案 A：Formspree（推荐，免费 50 条/月）

1. 注册 https://formspree.io
2. 创建新表单 → 获取 Form ID
3. 替换 `index.html` 中 `action="https://formspree.io/f/your-form-id"` 的 `your-form-id`
4. 在 Formspree Settings 中配置邮件通知

#### 方案 B：Google Forms（完全免费，无限量）

1. 创建 Google Form（称呼、联系方式、渠道、备注）
2. 点击"发送"→ 嵌入 HTML → 复制 iframe 代码
3. 替换 `index.html` 中 `<form id="signup-form">...</form>` 整个表单区域

### 3. 替换微信二维码

1. 在微信中：我 → 头像 → 二维码名片 → 截图
2. 替换占位符区域：
```html
<div style="width:160px; height:160px; background:var(--gray-200); ...">
  [微信二维码<br>请替换为<br>你的二维码图片]
</div>
```
为：
```html
<img src="your-qr-code.png" alt="微信二维码" style="width:160px; height:160px; object-fit:contain;">
```

---

## 免费部署方案

### 方案 A：GitHub Pages（推荐，完全免费）

```bash
# 创建一个独立仓库来托管 Landing Page
gh repo create stock-data-landing --public --description "A股盯盘数据助手 Landing Page"
cp landing-page/index.html stock-data-landing/
cd stock-data-landing
git init && git add . && git commit -m "Add landing page"
git push origin main

# 然后在 GitHub 仓库 Settings → Pages
#   Source: Deploy from a branch
#   Branch: main
#   获得 URL: https://<username>.github.io/stock-data-landing
```

### 方案 B：Vercel（免费，支持自定义域名）

1. 将 `landing-page/` 目录推送到 GitHub
2. 在 https://vercel.com 导入该仓库
3. Root Directory 设置为 `landing-page`
4. 自动部署，获得 `xxx.vercel.app` 域名

### 方案 C：Cloudflare Pages（免费，国内访问较快）

1. 将代码推送到 GitHub
2. https://pages.cloudflare.com → 连接仓库
3. Build settings: 无需构建，直接部署静态文件
4. 获得 `xxx.pages.dev` 域名

---

## 部署后检查清单

- [ ] 浏览器访问 URL，页面正常显示
- [ ] 手机浏览器打开，移动端适配正常
- [ ] 提交测试表单 → 收到邮件通知
- [ ] 合规声明清晰可见
- [ ] 所有链接可点击
- [ ] 微信二维码显示正确

---

## 推广准备

部署完成后，准备以下素材（详见 Day 8）：

1. **微信群分享文案** — 3 个版本（直白版 / 故事版 / 数据版）
2. **雪球/知乎帖子** — 定位"散户数据工具"，非"荐股神器"
3. **闲鱼 listing** — 标题"飞书股票数据监控"，定价 9.9 元测试需求
