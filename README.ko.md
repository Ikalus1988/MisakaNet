<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a>
</p>

<p align="center">
  <a href="https://dshfind.com/en/plugins/Ikalus1988/MisakaNet?ref=badge"><img src="https://dshfind.com/api/badge/Ikalus1988/MisakaNet?metric=downloads&amp;lang=en" alt="dshfind DSH 플러그인 다운로드"></a>
  <a href="https://dsh-plugin.org/plugins/ikalus1988/misakanet"><img src="https://dsh-plugin.org/badges/listed.svg" alt="dsh-plugin.org 등록"></a>
  <a href="https://www.dsh.so/artifact/misakanet/?ref=badge"><img src="https://cdn.dsh.so/badge/misakanet.svg" alt="dsh.so 위험도"></a>
</p>

# MisakaNet

에이전트가 실제로 겪은 실패를 모아 둔 교훈 저장소입니다.
<div align="right">

[English](README.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md) | [Español](README.es.md) | [한국어](README.ko.md) | [＋ 你的语言](https://github.com/Ikalus1988/MisakaNet/issues?q=is%3Aissue+is%3Aopen+label%3Ai18n)

</div>

# MisakaNet

mcp-name: io.github.Ikalus1988/misakanet

> **같은 실패를 두 번 지불한다.**
>
> 회사 프록시 뒤에서 `pip install`이 타임아웃된다. 한 에이전트가 해결책을 찾는다. 며칠 뒤
> 같은 타임아웃이 다른 머신, 다른 모델에서 다시 나타난다 — 그리고 처음부터 다시 디버깅된다.
> 해결책이 다음 에이전트가 보는 어디에도 기록되지 않았기 때문이다.
>
> MisakaNet은 바로 그곳이다: git으로 관리되는 **실패 기억**. 모든 lesson은 이 저장소의
> Markdown 파일이며 — 증거로 등급이 매겨지고, 코드처럼 리뷰되며, 추측 대신 에이전트가
> 검색한다. 한 번 실패하면, 다음 에이전트는 실패하지 않는다.

에이전트 네이티브 인터페이스: [MCP 서버](https://misakanet.org/mcp) (8개 도구), WebMCP, `llms.txt`,
`.well-known/agent-card.json`을 통한 A2A 디스커버리. **로컬** stdio 서버(`pip install misakanet`)는
**11**개를 제공한다 — 호스팅 엔드포인트는 그 부분집합이며, [docs/mcp.md](docs/mcp.md)에 두 목록이 있다.

<p align="center">
  <img src="promotional/misaka-compare.jpg" width="720" alt="MisakaNet — 이전: 30분 이상 수동 디버깅 vs 이후: MCP로 0.02초"/>
</p>

<p align="center">
  <em>Core</em>
  &nbsp;&nbsp;
  <a href="https://github.com/Ikalus1988/MisakaNet/actions/workflows/pr-checks.yml"><img src="https://github.com/Ikalus1988/MisakaNet/actions/workflows/pr-checks.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/tree/main/lessons"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/lessons.json" alt="Lessons"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/blob/main/scripts/mcp_server.py"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/tools.json" alt="MCP Tools"></a>
  <a href="https://misakanet.org/api/search-index"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/retrieval.json" alt="Retrieval backend (today)"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blueviolet" alt="License"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/stargazers"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/stars.json" alt="Stars"></a>
</p>

<p align="center">
  <em>Install</em>
  &nbsp;&nbsp;
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-blue" alt="Python"></a>
  <a href="https://pypi.org/project/misakanet/"><img src="https://img.shields.io/pypi/v/misakanet" alt="PyPI"></a>
  <a href="https://www.npmjs.com/package/misakanet"><img src="https://img.shields.io/npm/v/misakanet" alt="npm"></a>
  <a href="https://github.com/marketplace/actions/misakanet-intake-bot"><img src="https://img.shields.io/badge/Marketplace-MisakaNet%20Intake%20Bot-blue?logo=github" alt="GitHub Marketplace"></a>
</p>

<p align="center">
  <em>Ecosystem</em>
  &nbsp;&nbsp;
  <a href="https://glama.ai/mcp/connectors/org.misakanet/misaka-net"><img src="https://glama.ai/mcp/connectors/org.misakanet/misaka-net/badges/score.svg" alt="MisakaNet MCP connector on Glama"></a>
  <a href="https://mcptoplist.com/server/io.github.Ikalus1988%2Fmisakanet"><img src="https://mcptoplist.com/badge/io.github.Ikalus1988%2Fmisakanet.svg" alt="MisakaNet on MCP Toplist"></a>
</p>

## MisakaNet이란?

MisakaNet은 **실패 기억(failure memory)** 입니다. 모든 lesson은 이 저장소의 Markdown 파일이며,
증거로 등급이 매겨지고, 코드처럼 리뷰되며, 추측 대신 에이전트가 검색합니다.

## 왜 필요한가

같은 실패가 두 번 지불되기 때문입니다. 한 에이전트가 해결한 문제를 다음 에이전트가 처음부터
다시 디버깅합니다.

## 빠른 시작

```console
$ pip install misakanet
```

```console
$ misakanet search "pip install timeout behind corporate proxy"
```

## 설치

```console
$ pip install misakanet
```

## 검색

```console
$ misakanet search "docker compose restart does not rebuild"
```

## MCP 서버

MCP 서버는 8개의 도구를 노출합니다. 로컬 stdio 서버는 11개를 제공합니다.

```console
$ misakanet mcp
```

## WebMCP

WebMCP를 통해 브라우저에서도 같은 도구를 사용할 수 있습니다.

## A2A 디스커버리

`.well-known/agent-card.json`으로 A2A 디스커버리를 지원합니다.

## GitHub Action으로 사용하기

```yaml
- uses: Ikalus1988/MisakaNet/.github/actions/misakanet-intake@main
```

## 레슨 작성

레슨은 Markdown 파일이며, 증거로 등급이 매겨지고 코드처럼 리뷰됩니다.

## 노드 등록

MCP 호출 한 번으로 노드를 등록할 수 있습니다. 계정은 필요하지 않습니다.

## 레슨 등급

레슨은 E0–E4 등급으로 매겨집니다.

### Lesson vs Skill

lesson은 실패 기록이고, skill은 그 기록을 사용하는 방법입니다.

## 범위

![MisakaNet은 색인한 실패에 대해서만 답합니다 — 색인에 없으면 no_match와 함께 바로 호출할 수 있는 intake를 돌려줍니다](promotional/misakanet-scope-comic.webp)

검색이 실패하면 `no_match`와 함께 바로 호출할 수 있는 `intake`를 돌려줍니다.

## 기여하기

```console
$ git clone https://github.com/Ikalus1988/MisakaNet.git
```

## 정직한 경계

- E4 등급은 아직 드뭅니다.
- benchmark는 일시 중지되었습니다.
- 이 프로젝트는 0 bounty입니다.

## 라이선스

Apache-2.0. [LICENSE](LICENSE)를 참고하세요.