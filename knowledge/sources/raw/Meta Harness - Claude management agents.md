Anthropic이 새로운 Harness 엔지니어링 사례 연구 기사를 발표했습니다.

https://www.anthropic.com/engineering/managed-agents
https://x.com/RLanceMartin/status/2041927992986009773


겉보기에는 그들의 신제품을 소개하는 것처럼 보이지만, 더 거시적인 관점에서 이 기사를 보면 본질적으로 하나의 문제를 탐구하고 있습니다: 모델 능력이 지속적으로 변화할 때, Agent 시스템은 대체 무엇을 "안정적인 인터페이스"로 만들어야 하며, 무엇을 미래의 끊임없는 재작성에 맡겨야 할까요?

기사를 다 읽고 나니, 이 기사가 Anthropic의 미래 Agent 인프라에 대한 깊은 판단을 숨기고 있다는 생각이 들었습니다: Agent 인프라는 점점 "미니 운영체제(Agent OS)"처럼 될 거예요. 이게 제가 가장 주목할 만하다고 여기는 부분입니다.

Agent 프레임워크에서 가장 피해야 할 것은 "일시적인 모델 결함"을 "영구적인 시스템 구조"로 승격시키는 것입니다.

harness(스케줄링 루프, 컨텍스트 정리, 도구 라우팅 등)는 본질적으로 모델 능력 경계에 대한 가정을 코드화하는 거지만, 이러한 가정들은 모델이 강해짐에 따라 빠르게 시대에 뒤떨어집니다.

"모델 능력이 강할수록, harness는 더 간단해질 것입니다."

하지만 지금 많은 사람들이 Agent를 작성할 때, 저를 포함해서, 모델 결함을 Agent 프레임워크에 쉽게 새겨버립니다. 예를 들어, 모델이 계획을 세우지 못하면 강제로 단계를 고정된 DAG로 분해하는 식이죠.. 등등.

이것들은 사실 harness 패치에 불과하고, 우리 agent 개발자들도 모델 결함이 무엇인지 판단하기 어렵습니다.

Anthropic의 접근은 meta-harness를 설계하는 것입니다: 구체적인 harness가 어떻게 생겼는지 약속하지 않고, 단지 몇 가지 장기적으로 안정적인 인터페이스만 약속합니다.

이렇게 하면 우리는 모델 결함이 무엇인지 추측할 필요가 없어요. 이건 OS 사고방식과 비슷합니다. OS는 미래 프로그램이 어떻게 작성되는지 전혀 신경 쓰지 않고, 단지 추상 인터페이스를 제공할 뿐입니다.

그렇다면 Anthropic의 이 meta-harness는 Agent에게 어떻게 추상을 제공할까요?

기사에서 가장 중요한 추상은 세 가지입니다:

- session, 이벤트 로그 / 영속 상태로 이해할 수 있습니다
- harness, 추론-스케줄링 루프 / 뇌간
- sandbox, 실행 환경 / 손발

이들의 분리가 바로 이 아키텍처의 핵심 혁신 포인트입니다.

1. The session is not Claude’s context window 

기사에서 이 문장은 meta-harness가 session을 어떻게 추상화하는지를 대표합니다. 그것은 단순한 채팅 기록이 아니라, 「복구 가능한 이벤트 흐름」을 나타냅니다.

Anthropic이 하고자 하는 것은 session을 append-only 이벤트 로그로 만드는 것입니다. 그것을 모델에 직접 입력하는 프롬프트로 취급해서는 안 되며, 쿼리 가능하고, 재생 가능하고, 복구 가능하고, 재구성 가능한 진짜 실행 이력이어야 합니다.

만약 session을 단순히 컨텍스트 윈도우의 미러로만 취급한다면, 그것은 복구 가능성을 잃어버린 셈입니다.

2. Harness：가장할 수 있는 오케스트레이션 레이어

초기 Anthropic은 harness, session, sandbox를 하나의 컨테이너에 모두 넣었습니다. 하지만 이렇게 하니 많은 문제가 생겼어요. 예를 들어, harness가 무너지면 전체 세션이 복구하기 어렵고; 컨테이너가 다운되면 상태가 손실될 수 있고; 디버깅이 어렵고, 사용자 데이터가 포함되어 있어서 shell로 쉽게 디버깅할 수 없으며; VPC 접근이 어렵습니다.

그래서 그들은 harness를 컨테이너에서 꺼내 "도구를 호출하는 뇌간"으로 만들었습니다.

이제 Harness는:

- 더 이상 상태를 소유하지 않습니다
- 도구가 어디에 있는지 가정하지 않습니다. 당신은 execute(name, input) -> string이라는 인터페이스만 볼 수 있습니다 (nix 철학 같은 느낌이네요)

Harness를 이렇게 추상화하는 의미는: AI는 자신이 어떤 장치에 있는지, 어떤 운영체제인지, 휴대폰인지 컴퓨터인지, 컨테이너인지 가상 머신인지 알 필요가 없습니다. 그것은 단지 "내가 어떤 손을 사용할 수 있는지"만 알 뿐입니다. (천수관음 생각해보세요..)

3. Sandbox：“어떤 구체적인 손”

기사에서 말하길, decouple the brain from the hands 

즉:

- Claude + harness는 brain입니다
- sandboxes / tools / MCP / custom infra는 hands입니다

sandbox가 단순히 hand일 뿐이라면, 그것들은 서로 독립적일 수 있고, 서로 다른 인프라에서 올 수 있으며, 공유하고 전달할 수도 있고, 매 세션마다 완전한 sandbox를 로드하고 시작할 필요도 없습니다.

이것이 바로 뒤의 "many brains, many hands"로 이어집니다.

이번 Anthropic의 사례는 현대 분산 시스템의 가장 핵심적인 경험 중 하나에서 나왔습니다: 특정 프로세스를 보존하려 하지 말고, 복구 가능한 사실 기록과 재시작 프로토콜을 보존하세요.

이렇게 설계하면 아키텍처적으로 보안성도 강화됩니다. 기사에 이런 문장이 있어요,

narrow scoping is an obvious mitigation, but this encodes an assumption about what Claude can't do with a limited token—and Claude is getting increasingly smart.

의미는:

- 물론 모델에게 "범위가 작은 토큰"을 줄 수 있습니다
- 하지만 이는 여전히 모델이 특정 공격 경로를 실행할 수 없다는 가정을 내포합니다
- 그런데 모델이 지속적으로 강해지면서, 이런 "그건 생각 못 하겠지"라는 보안 가정은 점점 취약해집니다

그래서 그들은 자격 증명을 sandbox에 넣지 않습니다. 예를 들어 Git 토큰은 초기 clone/push/pull 과정에서만 제어된 방식으로 접근되며, 모델이 토큰을 직접 읽지 못하게 합니다. 모델은 MCP 프록시를 통해 간접 호출하고, 프록시는 세션 토큰으로 vault에서 실제 자격 증명을 가져와 실행합니다.

보안을 모델 능력 부족에 기반하지 않게 하는 거예요.

이렇게 설계하면 "복구 가능한 역사"도 "컨텍스트 윈도우"에서 해방됩니다.

그 이념은, 전체 역사를 모델 컨텍스트에 넣지 말라는 것입니다; 그것을 쿼리 가능한 객체인 session에 넣으세요.

시스템 관점에서:

- Claude의 컨텍스트 윈도우는 실행 현장입니다
- session 로그는 증거 창고입니다
- harness는 검색 및 재구성기입니다

따라서:

- 프롬프트는 더 이상 "영구 기억" 역할을 하지 않습니다
- 트리밍은 역사 소실을 의미하지 않습니다
- 압축은 사실 복구 불가능을 의미하지 않습니다

복구 시 원시 이벤트를 다시 가져올 수 있어서, 이는 "순수 요약 메모리"보다 한 단계 높은 설계입니다.

이렇게 설계하면 성능도 향상됩니다.

TTFT(Time to First Token)를 낮추고, 매 세션마다 전체 컨테이너 비용을 선납하지 않게 됩니다.

이제 brain을 먼저 시작하고, hand는 필요할 때만 프로비저닝합니다. 이는 전형적인 lazy materialization 사고방식입니다.

기사에서 제시한 데이터도 아주 인상적입니다:

- p50 TTFT 약 60% 감소
- p95 90% 이상 감소

이 숫자는 하나의 문제를 드러냅니다: 원래 병목은 모델 추론 자체가 아니라, 전체 실행 환경을 요청 진입점에 미리 결합시킨 것이었습니다.

마지막으로, 이런 설계의 초점이 미래 Agent의 확장성을 강화하기 위한 것임을 잊지 마세요.

기사 마지막에 "Many brains, many hands"라고 합니다.

이는 Anthropic이 미래에 agent 런타임 기층을 만들려 한다는 의미입니다. 다중 뇌 협업 / 다중 손 오케스트레이션 / 교차 환경 실행.

Agent의 본체는 특정 실행 껍데기에 묶이지 말고, 복구 가능한 상태 집합과 호출 가능한 능력 집합에 묶여야 합니다.

기사에서 이런 설계의 단점도 언급했어요. 예를 들어 brain이 many hands를 관리하는 건 그 자체로 더 어려운 인지 작업입니다.

그래서 이 아키텍처의 전제는, 모델 지능이 충분히 높아서 더 추상적인 도구 라우팅 책임을 질 수 있다는 것입니다.

이건 사실 미래 모델 능력이 반드시 향상될 거라는 베팅이며, 미래 지향적 설계입니다.

마지막으로, 이 기사가 제게 준 영감은 세 가지입니다:

- 영감 1: 세션은 메시지 목록이 아니라 "실행 사실 흐름"입니다.
- 영감 2: 도구 환경을 agent 자체로 내재화하지 마세요.
- 영감 3: 컨텍스트 엔지니어링은 harness의 교체 가능한 전략이어야 하며, 미래에 모델이 강해지거나 검색 전략이 바뀌어도 기술 부채가 생기지 않게 고려하세요.

이 기사는 명확히 말하지 않았지만, 제 생각에 그것이 진짜 대표하는 것은 Anthropic의 제품 철학입니다: 우리는 오늘의 agent harness가 최종 형태가 아닐 거라 믿으므로, 일회성 최적 구현이 아니라 안정 인터페이스에 우선 투자합니다.

Agent 시스템의 미래는 장기적으로 안정적인 시스템 추상 위에 있습니다.


Launching Claude Managed Agents
TL;DR – Claude Managed Agents is a pre-built, configurable agent harness that runs in managed infrastructure. You define an agent as a template – tools, skills, files / repos, etc. The agent harness and the infrastructure are provided for you. The system is designed to keep pace with Claude’s rapidly growing intelligence and support long horizon tasks. Some useful links:
Claude blog: Usage patterns and customer examples
Engineering blog: The design of Claude Managed Agents
Docs: Onboarding, quickstart, overview of the CLI and SKDs 
Why Claude Managed Agents
The Claude messages API is a direct gateway to the model: it accepts messages and returns content blocks. Agents built on the messages API use a harness to route Claude’s tool calls to handlers and manage context. This poses a few challenges:
Harnesses need to keep up with Claude – I recently wrote a blog here focused on building agents using Claude API primitives to handle tool orchestration and context management. But agent harnesses encode assumptions about what Claude can’t do. These assumptions grow stale as Claude gets more capable and can bottleneck Claude’s performance. Harnesses need to be continually updated to keep pace with Claude.
Claude is running for longer  – Claude’s task horizon is growing exponentially, already exceeding over 10 human-hours of work on the METR benchmark. This puts pressure on the infrastructure around an agent: it needs to be safe, resilient to infrastructure failures that happen over long horizon tasks, and support scaling (e.g., to many agent teams).
Addressing these challenges is important because we expect future Claude to run over days, weeks, or months on humanity's greatest challenges. The Claude Agent SDK was a first step, providing an excellent general purpose agent harness. Claude Managed Agents is the next step in this progression: a system with the harness and managed infrastructure designed to support safe, reliable execution over the time-horizon that we expect Claude to work.
How to get started
An easy way to onboard is to use our open source claude-api skill, which works out of the box in Claude Code. Get the latest version of Claude Code and run the following sub-command for Claude Managed Agents onboarding. I’m excited about skills as a way to onboard to new features, and have used this skill extensively:
json
$ claude update
$ claude
/claude-api managed-agents-onboarding
Also see our docs for quickstart with the SDKs or CLI, and prototype agents in Claude Console.
Use cases
You can see our Claude blog for a number of interesting examples. Some of the common patterns I’ve noticed across these examples and my own work:
Event-triggered: A service triggers the Managed Agent to do a task. For example, a system flags a bug and a managed agent writes the patch and opens the PR. No human in the loop between flag and action.
Scheduled: Managed Agent is scheduled to do a task. For example, I and many others use this pattern for scheduled daily briefs (e.g., of X or Github activity, what a team of agents is working on). Here's an example daily brief of X activity that I use.
Fire-and-forget: Humans trigger the Managed Agent to do a task. For example, assign tasks to the Managed Agent via Slack or Teams and get back deliverables (spreadsheets, slides, apps).
Long-horizon tasks: Long-running tasks are an area where I think Managed Agents will be particularly useful. I’ve explored this by forking @karpathy's auto-research repo and exploring a few different ideas. For example, I recently took @_chenglou’s excellent pretext library and had a Managed Agent explore ways to apply it to our engineering blog content.
Key concepts
When onboarding, there’s three central concepts to understand:
Agent — A versioned config that houses the agent's identity: model, system prompt, tools, skills, MCP servers, etc. You create it once and reference it by ID.
Environment — A template describing how to provision the sandbox the agent's tools run in (e.g., runtime type, networking policy, and package config).
Session — A stateful run using the pre-created agent config and environment. It provisions a fresh sandbox from the environment template, mounts any per-run resources (files, GitHub repos), stores auth in a secure vault (MCP credentials).
Think about an agent  as a configuration, an environment as a template describing the sandbox you want the agent to access for code execution, and the session as any agent execution. One agent can have many sessions.
Usage
See docs here:
SDKs – These are code-facing: import them in your app to drive sessions at runtime. Six languages have Managed Agents support: Python, TypeScript, Java, Go, Ruby, PHP.
CLI – Terminal-facing: every API resource (agents, environments, sessions, vaults, skills, files) is exposed as a subcommand.
Common patterns – Use the CLI for setup and SDK for runtime. Agents templates are persistent: you create one, store it (e.g., as a YAML with model, system prompt, tools, MCP servers, skills in git) and have the CLI apply it in your deploy pipeline.
How it works
I wrote an Anthropic engineering blog post with @mc_anthropic, @gcemaj, and @jkeatn on the process of building Claude Managed Agents: a lesson we share in the post is  that building agents to scale with Claude’s intelligence is an infrastructure challenge, not strictly a matter of harness design.
With this in mind, we didn’t design a particular agent harness; we expect agent harnesses to constantly evolve. Instead we decouple what we thought of as the “brain” (Claude and its harness) from both the “hands” (sandboxes and tools that perform actions) and the “session” (the log of session events). 
Each became an interface that made few assumptions about the others, and each could fail or be replaced independently. We share how this gives the system reliability, security, and flexibility to add future harnesses, sandboxes, or infrastructure to house sessions. 
Conclusion
I'm excited about projects exploring different patterns of multi-agent orchestration or long-running tasks. One of the frustrations I've written about in the past is keeping agent harnesses up with model capabilities. Claude Managed Agents handles the agent harness and infrastructure for you, allowing for explorations on top of the agent as a new core primitive in the Claude API.