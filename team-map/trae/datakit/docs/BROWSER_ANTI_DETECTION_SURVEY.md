# 浏览器反检测方案调研报告

> 2026-07-07 | 针对 browser-use MCP 无头模式被反爬识别问题的全网调研

---

## 一、问题诊断：为什么 browser-use 会被识别？

`browser-use` 底层使用的是 `chrome-devtools-mcp`（Google 官方 Chrome DevTools Protocol MCP），它的致命指纹泄漏路径：

```
browser-use
  └── chrome-devtools-mcp (Google 官方)
        └── Playwright/Puppeteer 驱动 Chrome
              └── navigator.webdriver = true  ← 🔴 第一条泄漏
              └── CDP Runtime.enable 调用序列  ← 🔴 第二条泄漏
              └── HeadlessChrome UA 标记       ← 🔴 第三条泄漏
              └── 缺失的插件/字体/WebGL 指纹    ← 🔴 第四条泄漏
```

**官方确认**：ChromeDevTools MCP 仓库 Issue #553 中，多位开发者反馈即使设置 `--headless=false` 和 `--disable-blink-features=AutomationControlled`，仍然被 Cloudflare/DataDome 等反爬系统识别。官方暂未提供内置 stealth 方案。

---

## 二、GitHub 反检测工具谱系（按代际）

### 演进时间线

```
2019 ─ puppeteer-extra-plugin-stealth      JS 层打补丁（❌ 已过时）
2021 ─ undetected-chromedriver (UC)        修补 chromedriver 二进制
2023 ─ nodriver / zendriver                抛弃 Selenium，直连 CDP
2024 ─ Camoufox                            从 C++ 源码级修改 Firefox
2025 ─ SeleniumBase CDP Mode               CDP 但无 Playwright 中间件
2025 ─ puppeteer-real-browser (Rebrowser)  品牌 Chrome + 底层补丁
2026 ─ invisible_playwright                C++ 级 Firefox fork，drop-in 替换
```

---

## 三、主流方案详细对比

### 🥇 nodriver — 基准测试最强

| 维度 | 详情 |
|------|------|
| GitHub | `ultrafunkamsterdam/nodriver` |
| Stars | 8.5k+ |
| 原理 | 直连 Chrome CDP WebSocket，**零 Selenium/Playwright 中间层** |
| 语言 | Python 纯异步 (asyncio) |
| 反检测 | 28/31 Cloudflare Turnstile 通过，0 封禁（ianlpaterson 2026 基准测试） |
| 为什么强 | 去掉了 Playwright 的 `Runtime.enable` 调用序列指纹；CDP 握手序列不同于自动化工具 |
| 弱点 | 无法自动管理下载/弹窗（不如 Playwright 功能全） |
| 安装 | `pip install nodriver` |
| 与真实 Chrome 的关系 | 启动系统 Chrome 实例，**可使用系统 Chrome 的 cookie/profile** |

```python
# 最简示例
import asyncio
import nodriver as uc

async def main():
    browser = await uc.start()
    page = await browser.get("https://tickflow.org")
    # 使用已登录的系统 Chrome profile
    await page.wait(5)
    print(await page.evaluate("document.body.innerText"))

asyncio.run(main())
```

### 🥈 puppeteer-real-browser — 最适配 MCP + 真实 Profile

| 维度 | 详情 |
|------|------|
| GitHub | `ZFC-Digital/puppeteer-real-browser` |
| Stars | 1k+ |
| 原理 | 基于 Rebrowser 补丁，修补 Puppeteer 底层，用**品牌 Chrome**（非 Chromium）|
| 语言 | JavaScript (Node.js) |
| 关键优势 | ✅ **已有人做了 MCP Server**：`withLinda/puppeteer-real-browser-mcp-server` |
| 与真实 Profile | 直接使用系统 Chrome + 用户 Profile → **J先生的 Chrome 密码包直接可用** |
| ChromeDevTools MCP 官方推荐 | Issue #553 中 community 指向此方案 |
| 安装 | `npx puppeteer-real-browser-mcp-server@latest` |

```json
// MCP 配置 — Claude Code 直接接入
{
  "mcpServers": {
    "puppeteer-real-browser": {
      "command": "npx",
      "args": ["puppeteer-real-browser-mcp-server@latest"],
      "env": {
        "HEADLESS": "false",
        "CHROME_PATH": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "USER_DATA_DIR": "/Users/fiona/Library/Application Support/Google/Chrome"
      }
    }
  }
}
```

> ⚠️ **注意**：使用真实 Profile 时 Chrome 不能同时在运行（Chrome 锁文件冲突）

### 🥉 SeleniumBase CDP Mode — 功能最全

| 维度 | 详情 |
|------|------|
| GitHub | `seleniumbase/SeleniumBase` |
| Stars | 7k+ |
| 原理 | 纯 CDP 模式，绕过 WebDriver 协议；内置 PyAutoGUI 集成 |
| 反检测 | 2026 年视频演示：通过 Cloudflare Turnstile, DataDome, reCAPTCHA, hCaptcha, Friendly Captcha 全部 5 种 |
| 附加能力 | 内置 CAPTCHA solver、cookie 复用、移动端模拟、Docker 支持 |
| 安装 | `pip install seleniumbase` |

### 其他方案

| 工具 | Stars | 特点 | 局限 |
|------|-------|------|------|
| **Camoufox** | 1.5k | Firefox C++ 级 fork，真正的"另一种浏览器" | Firefox 生态，Chrome 密码包用不了 |
| **invisible_playwright** | 新 | Firefox fork，Playwright drop-in 替换 | 同上 |
| **stealth-browser-mcp** | 1.5k | Camoufox + Docker + PyAutoGUI | 部署重，需要 Docker |
| **undetected-chromedriver** | 9k+ | 经典方案，仍然能用 | 作者已转向 nodriver，不再积极维护 |
| **zendriver** | fork | nodriver 的活跃 fork | 文档少，API 同 nodriver |

---

## 四、针对 J先生 场景的推荐路径

### 场景特点
1. 需要访问 tickflow.org、iwencai.com 等需要登录的网站
2. Chrome 浏览器已保存密码
3. 通过 Claude Code 的 MCP 协议驱动
4. 不需要高频大规模爬取，而是偶发的登录+信息获取

### 推荐方案：puppeteer-real-browser-mcp-server

**理由**：
- ✅ 直接接入 Claude Code MCP 生态（一行 npx 配置）
- ✅ 使用 J先生 的真实 Chrome + Profile → 密码包立即可用
- ✅ Rebrowser 底层补丁对抗 Cloudflare/反爬
- ✅ HEADLESS=false 模式下浏览器窗口可见，手工介入也是自然的
- ✅ ChromeDevTools 官方 issue 中社区公认方案

### 备选：nodriver（如需 Python 原生控制）

如果需要一个 Python 脚本自己控制浏览器而非通过 MCP：
```bash
pip install nodriver
```
然后用 Python 脚本启动系统 Chrome，自动继承登录态。

---

## 五、底层原理：为什么 CDP 直连比 WebDriver 更隐蔽？

```
传统 Selenium/Playwright 路径：
  Python → WebDriver Protocol → ChromeDriver/Playwright Server → Chrome
          ↑ 有指纹                          ↑ 有指纹

nodriver / CDP Mode 路径：
  Python → Chrome DevTools Protocol (WebSocket) → Chrome
           ↑ 无 WebDriver 指纹，CDP 序列不同于自动化工具
```

关键差异：
1. **`navigator.webdriver`** — WebDriver 协议会设 true，CDP 直连不会
2. **`Runtime.enable` 调用序列** — Playwright 启动时的 CDP 命令序列有固定模式，可被检测
3. **品牌 Chrome vs Chromium** — Google Chrome 有 Widevine、H264 等 Chromium 缺失的 codec/license
4. **User-Agent 差异** — Headless Chrome UA 带 `HeadlessChrome` 标记

---

## 六、行动计划

```
1. 关闭当前运行的 Chrome（避免 Profile 锁）
2. 在 Claude Code MCP 配置中加入 puppeteer-real-browser-mcp-server
3. 重启 Claude Code → 新 MCP 工具出现
4. 用新工具打开 tickflow.org → 浏览器自动加载 J先生 的登录态
5. 完成定价调查
```

---

## 参考来源

- nodriver: https://github.com/ultrafunkamsterdam/nodriver
- puppeteer-real-browser: https://github.com/ZFC-Digital/puppeteer-real-browser
- puppeteer-real-browser MCP: https://github.com/withLinda/puppeteer-real-browser-mcp-server
- SeleniumBase CDP: https://github.com/seleniumbase/SeleniumBase
- ChromeDevTools MCP Issue #553: https://github.com/ChromeDevTools/chrome-devtools-mcp/issues/553
- Anti-detect benchmark 2026: https://ianlpaterson.com/blog/anti-detect-browser-benchmark-patchright-nodriver-curl-cffi
- Castle.io 反检测框架演进: https://blog.castle.io/from-puppeteer-stealth-to-nodriver-how-anti-detect-frameworks-evolved-to-evade-bot-detection
- BrightData puppeteer-real-browser 指南: https://brightdata.com/blog/web-data/puppeteer-real-browser
