# Academic Daily Scholar

Academic Daily Scholar 是一个面向教育研究的自动化学术日报系统。它会在每天北京时间上午 8 点优先检索近期英文期刊论文，按 SSCI 白名单、教育主题关键词、查重状态和排除规则筛选，再调用 OpenAI 兼容 API 生成中文精读摘要，最后通过网易 163 SMTP 发送 HTML 邮件，并在本地保存 Markdown 与真正的 Word .docx 文件。

## 功能概览

- 文献来源：OpenAlex API、Crossref REST API，不使用 Semantic Scholar API。
- 时间范围：默认优先检索近 3 天；不足时扩大到近 3 年历史窗口补充，但不会重复推荐 data/seen_papers.json 中已经出现过的论文。
- 排序与数量：按发布时间排序，最多保留 30 篇。
- 主题方向：小学数学教育、教师专业发展、教育技术、生成式 AI、LLM、ChatGPT、教师数字素养、乡村教师等。
- 排除方向：医学、材料、生物、机械、金融等无关领域。
- SSCI 白名单：支持读取本地 .xlsx 白名单，按期刊名与 ISSN 匹配，并尽量识别 JIF、JCR 分区、CiteScore、出版社和学科分类。
- 输出：daily/YYYY-MM-DD.md、daily/YYYY-MM-DD.docx、HTML 邮件。
- 日志：logs/today.log 和 logs/YYYY-MM-DD.log。
- 自动化：GitHub Actions 每天北京时间 08:00 自动运行，并支持 workflow_dispatch 手动触发。

## 项目结构

项目包含 main.py、config.py、search.py、filter.py、summarizer.py、translator.py、mailer.py、html_generator.py、markdown_generator.py、logger.py、utils.py、requirements.txt、README.md、.env.example、.github/workflows/daily.yml、templates/email.html.j2、tests/、daily/、logs/。

## ① 安装

建议使用 Python 3.12。

创建虚拟环境：

    python -m venv .venv

Windows PowerShell 激活：

    .\.venv\Scripts\Activate.ps1

macOS/Linux 激活：

    source .venv/bin/activate

安装依赖：

    python -m pip install --upgrade pip
    pip install -r requirements.txt

## ② 配置

复制环境变量示例：

    cp .env.example .env

Windows PowerShell：

    Copy-Item .env.example .env

编辑 .env：

    OPENALEX_API_KEY=你的OpenAlex API Key
    OPENAI_API_KEY=你的OpenAI兼容API Key
    OPENAI_BASE_URL=http://152.53.240.99:8080
    OPENAI_MODEL=gpt-5.5
    SMTP_SERVER=smtp.163.com
    SMTP_EMAIL=agonyy2026@163.com
    SMTP_AUTH_CODE=你的网易邮箱SMTP授权码
    MAIL_TO=agony2023@qq.com
    SSCI_WHITELIST_PATH=data/ssci_whitelist_2026-06.xlsx
    SSCI_FILTER_MODE=strict

说明：

- 程序不会在代码中写死 API Key 或邮箱授权码。
- .env.example 只保留字段名，不保存真实 API key；真实 key 请放在本地 .env 或 GitHub Secrets。
- SSCI_FILTER_MODE 可选 strict、prefer、off。
- strict：如果白名单文件可用，只保留白名单匹配论文。
- prefer：白名单论文优先，但非白名单教育相关论文也可保留。
- off：不使用白名单。
- 白名单文件已经放入仓库 data/ssci_whitelist_2026-06.xlsx，GitHub Actions 可直接读取。
- 默认 PRIMARY_SEARCH_DAYS=3，FALLBACK_SEARCH_YEARS=3。也就是说，系统不是严格“最近24小时”，而是“优先近期，不足时历史补充，并且不重复推荐”。

## ③ GitHub Secrets

进入 GitHub 仓库：

Settings → Secrets and variables → Actions → New repository secret

建议添加：

| Secret | 示例 |
|---|---|
| OPENALEX_API_KEY | OpenAlex API Key |
| OPENAI_API_KEY | sk-... |
| OPENAI_BASE_URL | http://152.53.240.99:8080 |
| OPENAI_MODEL | gpt-5.5 |
| SMTP_SERVER | smtp.163.com（可不设，默认值） |
| SMTP_EMAIL | agonyy2026@163.com |
| SMTP_AUTH_CODE | 网易 SMTP 授权码 |
| MAIL_TO | agony2023@qq.com |
| SSCI_WHITELIST_PATH | 通常不需要设置，工作流已固定为 data/ssci_whitelist_2026-06.xlsx |

注意：GitHub Actions 运行在 Linux 云端，不能读取你本机的 D:\SSCI期刊白名单_2026-06.xlsx。本项目现在已经把白名单复制到仓库 data/ 目录，因此云端可直接读取。

## ④ GitHub Actions

工作流文件位于 .github/workflows/daily.yml。

触发方式：

- 自动触发：每天 UTC 00:00，即北京时间 08:00。
- 手动触发：GitHub 仓库页面 → Actions → Academic Daily Scholar → Run workflow。

工作流会：

1. 安装 Python 3.12。
2. 安装 requirements.txt。
3. 执行 pytest。
4. 执行 python main.py check-config。
5. 执行 python main.py run-once。
6. 将生成的 daily/、logs/、data/seen_papers.json 上传为 GitHub Actions artifact，方便下载；默认不自动提交回仓库，以减少冲突。

## ⑤ 网易邮箱开启 SMTP 的方法

以 163 邮箱为例：

1. 登录网易邮箱网页版。
2. 进入设置。
3. 找到 POP3/SMTP/IMAP 或客户端授权密码。
4. 开启 SMTP 服务。
5. 按提示完成短信或安全验证。
6. 生成授权码。
7. 将授权码填入 .env 的 SMTP_AUTH_CODE，或填入 GitHub Secrets 的 SMTP_AUTH_CODE。

常用配置：

    SMTP_SERVER=smtp.163.com
    SMTP_EMAIL=agonyy2026@163.com
    SMTP_AUTH_CODE=你的授权码

## ⑥ 本地运行方法

检查配置：

    python main.py check-config

运行一次并发送邮件：

    python main.py run-once

只生成日报，不发送邮件：

    python main.py run-once --no-email

本地常驻定时运行：

    python main.py serve

serve 模式会使用 .env 中的 RUN_TIME=08:00 和 TIMEZONE=Asia/Shanghai。长期运行建议使用 Windows 任务计划程序、systemd、PM2、Docker 或 GitHub Actions。

## ⑦ 如何修改关键词

检索关键词在 search.py 的 SEARCH_QUERIES。

筛选保留关键词在 filter.py 的 INCLUDE_KEYWORDS。

排除关键词在 filter.py 的 EXCLUDE_KEYWORDS。

如果你希望更偏向“小学数学 + 教师专业发展”，可以增加 primary mathematics lesson study、elementary mathematics teacher learning、teacher knowledge mathematics education 等查询。

如果你希望更偏向生成式 AI，可以增加 generative artificial intelligence teacher education、large language models lesson planning、ChatGPT mathematics education 等查询。

## ⑧ 如何修改邮件模板

邮件模板位于 templates/email.html.j2。

它使用 Jinja2 渲染，可修改：

- 颜色与字体：style 中的 CSS。
- 目录：toc 区域。
- 每篇论文展示字段：report.items 循环内部。
- 运行统计：页面底部 stats 区域。

修改后可先运行：

    python main.py run-once --no-email

先检查 daily/YYYY-MM-DD.md 和 .docx 文件，再决定是否发送邮件。

## ⑨ 如何更换 OpenAI 兼容 API

只需要修改 .env 或 GitHub Secrets：

    OPENAI_API_KEY=sk-...
    OPENAI_BASE_URL=https://你的兼容接口/v1
    OPENAI_MODEL=你的模型名

要求该接口兼容 OpenAI Chat Completions，也就是支持 client.chat.completions.create 调用。

如果你的服务地址不带 /v1 也能兼容，直接按服务商文档填写即可；如果要求 /v1，请写完整。

## SSCI 白名单说明

白名单已复制到项目内路径：

    data/ssci_whitelist_2026-06.xlsx

程序会读取 .xlsx 文件中的表格文本，并自动识别：

- 期刊名列：包含 journal、source title、刊名、期刊、title 等表头。
- ISSN 列：包含 issn 的表头。
- 元数据列：尽量识别 journal_name、ISSN、JIF、JCR quartile、CiteScore、Publisher、Category 等表头。

匹配方式：

- 优先按 ISSN 匹配。
- 其次按规范化期刊名匹配。
- 对较长刊名支持包含式模糊匹配。
- 匹配成功后，报告会显示影响因子/JIF、JCR 分区、CiteScore、出版社和 SSCI 分类；如果白名单没有这些字段，则显示“白名单未提供”。

如果当前运行环境找不到该文件，会记录 warning，并根据 SSCI_FILTER_MODE 和主题筛选规则继续运行。

## 日志

日志会记录：

- 检索数量
- 筛选数量
- 成功数量
- 失败数量
- 邮件发送状态
- API 耗时

查看今日日志：

    type logs\today.log

macOS/Linux：

    cat logs/today.log

## 单元测试

运行：

    pytest

当前测试覆盖：

- DOI/ISSN 规范化。
- JSON 输出解析。
- SSCI 白名单 ISSN 匹配。
- 教育主题保留。
- 医学主题排除。

## 合法访问说明

本项目默认使用 OpenAlex 与 Crossref 官方公开 API。对 Springer、ScienceDirect、Taylor & Francis、Wiley、Nature、ERIC、Google Scholar 等网页来源，建议仅在符合其 robots.txt、服务条款和公开访问限制的前提下扩展。当前版本没有绕过登录、验证码、付费墙或访问限制。

## 常见问题

### 为什么说 SCI/SSCI 是近似自动化？

OpenAlex 和 Crossref 本身不提供 Web of Science 的 SCI/SSCI 收录状态字段。项目通过你提供的 SSCI 白名单进行期刊匹配；如果没有白名单，则只能依据期刊元数据、DOI、英文期刊论文类型和教育主题进行近似筛选。

### 没有检索到论文怎么办？

教育学论文每日新增数量不稳定。你可以：

- 将 SSCI_FILTER_MODE 改为 prefer。
- 扩展 SEARCH_QUERIES。
- 调整 PRIMARY_SEARCH_DAYS 或 FALLBACK_SEARCH_YEARS。
- 检查 OpenAlex/Crossref 是否临时限流。

### 邮件发不出去怎么办？

检查：

- 网易 SMTP 是否开启。
- 使用的是授权码，不是邮箱登录密码。
- 网易 SSL SMTP 默认使用 465 端口，通常不需要单独配置。
- GitHub Actions Secrets 是否填写正确。
- logs/today.log 中的 SMTP 错误信息。
