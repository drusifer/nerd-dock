# CHAT.md — Conversation Flow

Auto-generated from `agents/CHAT.md` by `bobp chat-diagram`. Do not edit by hand — regenerate with `make chat_diagram` (or it regenerates automatically on every `make chat`).

```mermaid
%%{init: {"sequence": {"messageFontSize": 14, "noteFontSize": 18, "actorFontSize": 14}}}%%
sequenceDiagram
    autonumber
    participant User
    participant All
    participant Cypher
    participant Morpheus
    participant Smith
    participant Mouse
    participant Neo
    participant Oracle
    Note over User,Oracle: 📅 2026-05-20
    User->>All: "request"
    Note right of User: "Req GNOME 50 dock widget<br/>for nerd-dictation (star<br/>t/stop/pause/resume).<br/>Python + GNU Make venv &<br/>test harness for Ubuntu<br/>26.04"
    Cypher->>Morpheus: "handoff"
    Note right of Cypher: "Defined PRD &<br/>implementation plan for<br/>nerd-dock. Handoff to<br/>@Morpheus to review<br/>architecture."
    User->>All: "request"
    Note right of User: "/bloop *plan product<br/>sprint"
    Cypher->>Smith: "pm handoff"
    Note right of Cypher: "Defined PRD and User<br/>Stories in docs/. @Smith<br/>*user review please<br/>review the stories."
    Smith->>Morpheus: "user approve"
    Note right of Smith: "HCI Review complete.<br/>Approved user stories<br/>for nerd-dock. Handoff<br/>to @Morpheus *lead arch<br/>sprint to draft<br/>architecture."
    Morpheus->>Smith: "lead handoff"
    Note right of Morpheus: "Completed architecture<br/>design in docs/ARCH.md.<br/>Handoff to @Smith *user<br/>review to review<br/>architecture impact on<br/>UX."
    Smith->>Mouse: "user approve"
    Note right of Smith: "Architecture approved!<br/>All systems go. Handoff<br/>to @Mouse *sm plan<br/>sprint to decompose<br/>phases in task.md."
    Mouse->>Morpheus: "sm plan"
    Note right of Mouse: "Sprint tasks decomposed<br/>in task.md. Handoff to<br/>@Morpheus *lead review<br/>sprint plan to review<br/>sprint plan vs<br/>architecture."
    Morpheus->>User: "lead approve"
    Note right of Morpheus: "Sprint plan reviewed and<br/>approved! Ready for<br/>Phase 1 implementation.<br/>Handoff to User."
    Cypher->>User: "pm update"
    Note right of Cypher: "Incorporated user<br/>feedback: focused on<br/>decorated system tray<br/>indicator, added Ruff/Ra<br/>don/Vulture/Bandit/Pylin<br/>t. Awaiting approval."
    User->>All: "approve"
    Note right of User: "[Approved]<br/>implementation_plan.md"
    Neo->>All: "swe impl"
    Note right of Neo: "Approved implementation<br/>plan. Entering Phase 1<br/>to set up the env & dev<br/>tools."
    Neo->>Neo: "handoff"
    Note right of Neo: "Completed Phase 1 (Setup<br/>& Dev Tools). Laid out<br/>nerd_dock package,<br/>pyproject.toml,<br/>Makefile.prj, and tests/<br/>with headless mocks.<br/>Test disco…"
    Note over User,Oracle: 📅 2026-05-22
    User->>All: "request"
    Note right of User: "/neo fix, there's no<br/>feedback when the nerd<br/>process is running."
    Neo->>User: "fix"
    Note right of Neo: "Aligned cookie paths by<br/>passing --cookie flag to<br/>nerd-dictation commands<br/>in controller. Fully<br/>tested and verified all<br/>lint and test suites…"
    Neo->>User: "fix"
    Note right of Neo: "Fixed the UI callback<br/>race condition via<br/>_current_ui_state<br/>tracking, and terminated<br/>any running nerd-<br/>dictation process inside<br/>shutdown() to…"
    Note over User,Oracle: 📅 2026-05-24
    User->>All: "request"
    Note right of User: "/oracle add user guide<br/>and readme content"
    Oracle->>User: "handoff"
    Note right of Oracle: "Completed documentation<br/>sprint. Added README.md<br/>and docs/USER_GUIDE.md,<br/>and updated agent<br/>documentation index.<br/>Handing back to User for<br/>ver…"
    User->>All: "request"
    Note right of User: "fix mermaid in README.md"
    Oracle->>User: "handoff"
    Note right of Oracle: "Fixed Mermaid syntax in<br/>README.md by quoting<br/>node labels containing<br/>special characters.<br/>Handing back to User for<br/>verification. @User<br/>*verify"
    User->>All: "request"
    Note right of User: "add make for system<br/>install"
    Oracle->>User: "handoff"
    Note right of Oracle: "Added make install-<br/>system-deps to<br/>Makefile.prj to automate<br/>system dependencies.<br/>Updated README.md and<br/>USER_GUIDE.md to<br/>document this. Handi…"
    User->>All: "request"
    Note right of User: "i want a target to<br/>install nerd-doc on the<br/>current system (pythonic<br/>way)"
    Oracle->>User: "handoff"
    Note right of Oracle: "Added make install to<br/>Makefile.prj to support<br/>pythonic active-<br/>environment package<br/>installation. Updated<br/>README.md and<br/>USER_GUIDE.md to docu…"
    User->>All: "request"
    Note right of User: "i will install to system<br/>with pipx but you need<br/>to fix this first:<br/>Multiple top-level<br/>packages discovered<br/>error."
    Oracle->>User: "handoff"
    Note right of Oracle: "Resolved pipx<br/>installation issue by<br/>explicitly defining<br/>packages and package-<br/>data in pyproject.toml<br/>to avoid flat-layout<br/>auto-discovery con…"
```
