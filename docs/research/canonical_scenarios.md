# Canonical Multi-Robot Coalition-Formation Scenarios

Research snapshot: 2026-09-03

## Executive finding

There is no single, broadly accepted coalition-formation benchmark suite analogous to a standard control benchmark. The literature is split among abstract coalition allocation, multi-robot task allocation (MRTA), coalition routing and scheduling, cooperative manipulation, and domain simulators such as RoboCup Rescue. A useful universal toolkit should therefore implement a small basis of problem features and expose several literature-derived scenario families through the same interface.

The recommended core suite is:

1. **Static capability matching** — the minimal coalition-formation problem and an exact-solver oracle.
2. **Spatial rendezvous and cooperative transport** — geometry, synchronized arrival, and tightly coupled execution.
3. **Coalition Formation with Spatial and Temporal constraints (CFSTP)** — repeated formation/disbanding, routing, workload, deadlines, and coalition productivity.
4. **RoboCup Rescue-lite** — dynamic tasks, heterogeneous roles, precedence, partial observability, failures, and limited communication.
5. **Scheduled surveillance** — overlapping coalitions, concurrent sensing tasks, and synchronization.
6. **Dynamic incident streams** — open-world arrivals, stochastic travel/service, large teams, and distributed algorithms.

The first four form the strongest MVP: together they range from a mathematically checkable allocation problem to a dynamic, spatial, heterogeneous mission.

## Scope: what “coalition formation” means here

A coalition is a task-oriented group of robots that forms because the task cannot be performed, or cannot be performed as well, by a single robot. It may disband and reform after the task. This is distinct from:

- geometric formation control, where robots maintain a shape;
- generic multi-agent path finding, where each task normally needs only one robot;
- homogeneous swarming with no explicit task-oriented group membership; and
- coalition-structure games with no embodiment, unless used as an allocation model.

These neighboring problems should be integrable as motion, execution, or algorithm plugins, but should not define the core abstraction.

## Taxonomic foundation

Gerkey and Mataric classify MRTA along three axes:

- **ST/MT**: a robot can execute one task or multiple tasks concurrently;
- **SR/MR**: a task needs one robot or multiple robots; and
- **IA/TA**: an assignment is instantaneous or time-extended.

The canonical static coalition problem is **ST-MR-IA**. It can be formulated as set partitioning over feasible coalition-task pairs and is strongly NP-hard. Spatial scheduling produces **ST-MR-TA** or, when robots can support concurrent tasks, **MT-MR-TA**.

Korsah, Stentz, and Dias extend this view with the iTax dependency classes:

- **ND**: no dependencies;
- **ID**: a choice depends on the same robot's schedule;
- **XD**: a choice depends on other robots' schedules; and
- **CD**: task decomposition and allocation are coupled through complex dependencies.

Nunes et al. further separate time-extended problems with **time windows (TW)** from those with **synchronization and precedence (SP)**, and distinguish hard/soft and deterministic/stochastic constraints. This combined vocabulary is a good metadata scheme for scenario declarations.

## Canonical scenario families

### S0. Static capability matching

**Question:** Which disjoint coalitions should perform which simultaneously available tasks?

Each robot supplies a capability or resource vector. Each task has a requirement vector and reward. A coalition-task pair is feasible when the coalition's aggregated capabilities satisfy the task. Utilities may be additive, subadditive, superadditive, or supplied by a black-box evaluator.

This is the smallest scenario that is genuinely coalition formation. It isolates combinatorial allocation from motion and execution, supports brute-force checking on tiny instances, and is the right target for exact set-partitioning/MILP, greedy, market, and learning-based allocators.

Suggested presets:

- `tiny`: 6 robots, 3 skills, 3 tasks; hand-authored unique optimum;
- `small`: 12 robots, 5 skills, 8 tasks; multiple feasible partitions;
- `rachna_style`: resource-vector tasks and heterogeneous service providers, including a reproduction-scale preset inspired by the reported 68-robot, 10-service, 100-task RACHNA experiment.

Required variations: scarce skill, redundant skill, incompatible robot pair, coalition-size penalty, and multiple equally optimal partitions.

**Literature role:** Gerkey and Mataric identify ST-MR-IA with set partitioning. Vig and Adams' RACHNA work treats robots as service providers and tasks as resource demands in a market-based coalition mechanism.

### S1. Spatial rendezvous and cooperative transport

**Question:** Which coalition can assemble and jointly execute a task at lowest cost or earliest completion time?

Robots begin at different locations. A task requires a coalition to arrive within a synchronization tolerance. A transport or box-pushing task then requires the coalition to remain engaged while an object moves to a goal. Capability profiles can distinguish localization, perception, pushing, grasping, and communication.

Suggested presets:

- `rendezvous`: one task, heterogeneous speeds, one required capability combination;
- `single_box`: one oversized object requiring two or more robots;
- `blocked_boxes`: five robots in three capability profiles and two box tasks, with one box obstructing the other and therefore inducing precedence;
- `multi_object`: several transport tasks whose coalition sizes depend on object mass or geometry.

The simulation should support two execution fidelities: an analytical travel/service model for fast benchmarking and a simple 2-D kinematic model for visibly synchronized motion. Full contact physics is an optional later backend, not a prerequisite for coalition-algorithm research.

**Literature role:** Parker and Tang use multi-robot transportation and box pushing to validate ASyMTRe; the later IQ-ASyMTRe example uses five robots of three sensor/capability types and dependent box-pushing actions. The wider heterogeneous-robot survey identifies object transport and box pushing as recurring tightly coordinated tasks.

### S2. CFSTP disaster response

**Question:** How should a small population of agents repeatedly form, disband, route, and reform coalitions to finish many spatial tasks before deadlines?

Each task has a location, workload, deadline, and optional reward. Each coalition has a task-dependent productivity function. Robots travel between tasks; work accumulates only under the configured execution rule. The baseline objective is the number or reward of tasks completed by their deadlines.

The original CFSTP study supplies a reproducible synthetic benchmark recipe:

- 300 tasks;
- 2 to 20 agents;
- a 50 by 50 grid with Manhattan travel time;
- deadlines sampled from `U(5, 600)`;
- workloads sampled from `U(10, 50)`;
- superadditive coalition values of the form `u(C) = k |C|`, with `k` sampled from `U(1, 2)`; and
- 100 generated instances at each agent count.

The toolkit should preserve that preset and add smaller exact-solver cases. It should also expose additive, subadditive, superadditive, and task-specific productivity models because coalition synergy is a defining part of the problem.

Suggested presets:

- `cfstp_tiny`: 4 robots, 8 tasks, exact optimum available;
- `cfstp_paper`: the original 50 by 50 random-grid recipe;
- `cfstp_heterogeneous`: per-task capabilities and robot-specific productivity;
- `cfstp_open`: task arrivals revealed during execution.

**Literature role:** Ramchurn et al. formalize CFSTP, give a MIP for small instances, and compare earliest-deadline-first with coalition look-ahead. Capezzuto et al. later develop efficient and distributed variants and publish code through Zenodo.

### S3. RoboCup Rescue-lite

**Question:** How do coalitions respond when incidents evolve, information is incomplete, tasks depend on other tasks, and communication is restricted?

Use an abstract city graph rather than attempting to reproduce the entire RoboCup simulator. Three robot types mirror the official domain:

- fire brigades suppress spreading fires;
- police clear blocked roads; and
- ambulance teams excavate and transport injured civilians.

Canonical dependencies include `clear-road -> reach-victim`, `excavate -> transport`, and competition between fire suppression and nearby rescue priorities. Multiple ambulances may be required to rescue a buried civilian before a health deadline. Incidents appear or worsen over time. Each robot observes only a local or communicated subset of world state.

Suggested presets:

- `rescue_clear_then_extract`: a small deterministic precedence test;
- `rescue_parallel_incidents`: competing fires, blockages, and victims;
- `rescue_comms_dropout`: bandwidth, range, delay, and packet-loss variants;
- `rescue_robot_failure`: failure followed by reallocation and coalition repair.

**Literature role:** RoboCup Rescue explicitly identifies dynamic task allocation, coalition formation, route planning, partial observability, and restricted communication as core research problems. CFSTP uses this disaster-response setting as its running motivation.

### S4. Scheduled surveillance

**Question:** Which possibly overlapping robot groups should monitor multiple events or regions, some continuously and some at synchronized times?

Robots patrol regions and can run a limited number of sensing/computation tasks concurrently. Tasks may require complementary sensors, simultaneous viewpoints, minimum baseline separation, or repeated checks. This is the canonical route to MT-MR-IA/TA and set-cover-like formulations in which coalition membership can overlap.

Suggested presets:

- `multisensor_events`: complementary sensors and concurrent event detection;
- `stereo_track`: two synchronized viewpoints per target;
- `periodic_patrol`: repeated time windows and overlapping assignments;
- `connectivity_aware`: coalitions must remain connected to a relay or base.

**Literature role:** Gerkey and Mataric use scheduled multi-event building surveillance to motivate MT-MR allocation. The temporal-constraint literature uses surveillance to motivate synchronization and strict time-window behavior.

### S5. Dynamic incident streams and stochastic execution

**Question:** How well does an online or distributed algorithm scale when tasks arrive continually and execution times are uncertain?

This family uses either synthetic arrivals or incident records. It adds release times, stochastic travel/service, cancellation, priority escalation, robot availability shifts, and failures. It is the stress benchmark for anytime and decentralized policies.

Suggested presets:

- `poisson_incidents`: seeded synthetic spatial arrivals;
- `rush_hour`: time-varying travel-time distributions;
- `lfb_replay`: adapter for the published London Fire Brigade-derived benchmark;
- `large_distributed`: up to 150 agents and 3,000 active tasks, matching the scale reported for distributed CFSTP evaluation.

**Literature role:** the D-CTS and MARSC work reports a public-record-derived dataset of 347,588 London Fire Brigade incidents/tasks and experiments up to 150 agents and 3,000 tasks. Basso et al. add multi-skilled robots, simultaneous coalition arrival, and stochastic travel-time buffers.

## One extensible problem model

The scenarios can share the following typed model without forcing every scenario to use every field.

### Robot specification and state

- stable identifier and robot type;
- reusable capabilities and consumable resources;
- pose or graph node, speed/travel model, payload, and energy;
- concurrent-task capacity;
- sensing/communication model;
- current coalition memberships, schedule, health, and availability.

### Task specification and state

- location or region;
- capability/resource requirements;
- release time, duration/workload, time window, and deadline;
- reward, priority, and failure penalty;
- minimum/maximum coalition size;
- coalition productivity/quality function;
- synchronization rule and execution preconditions;
- predecessor/successor relationships;
- progress, assignment, and terminal status.

### Pluggable models

- `CoalitionFeasibility`: validates capabilities, size, incompatibilities, and connectivity;
- `CoalitionValue`: returns productivity, reward, or a vector of qualities;
- `TravelModel`: Euclidean, Manhattan, graph shortest path, stochastic, or external motion planner;
- `TaskDynamics`: progress, degradation, spreading, or object motion;
- `ObservationModel`: global, local, noisy, delayed, or partial state;
- `CommunicationModel`: topology, range, bandwidth, delay, loss, and message accounting;
- `AllocationPolicy`: centralized or per-robot decision maker;
- `ExecutionPolicy`: navigation and within-task control;
- `Termination` and `Metrics` plugins.

An algorithm should receive an immutable observation and return a typed proposal or action. The simulator, not the algorithm, owns validation and state transitions. This prevents algorithm plugins from silently changing the problem definition.

## Recommended simulation architecture

Use a small deterministic domain kernel with an append-only event trace. Keep adapters and presentation outside the kernel.

1. **Scenario layer** loads a versioned YAML/JSON configuration or seeded generator.
2. **Kernel** applies events and actions, validates invariants, and records ground truth.
3. **Policy adapters** support centralized solvers, distributed agents, auctions, heuristics, and learned policies.
4. **Execution backends** provide allocation-only, graph-motion, and continuous 2-D modes.
5. **Trace consumers** compute metrics, certify feasibility, render media, and export tabular results.

Do not make Mesa, SimPy, Gymnasium, or PettingZoo the domain model. A custom kernel can expose optional adapters:

- a PettingZoo Parallel API for simultaneous decentralized or MARL actions;
- Gymnasium wrappers for centralized policies;
- a SimPy adapter if asynchronous process-style experiments need it; and
- a Mesa-facing dashboard if its agent-based visualization becomes useful.

This avoids coupling exact optimization experiments to an RL API or coupling deterministic benchmarks to a browser UI. PettingZoo is still the most useful compatibility target because its parallel interface permits heterogeneous per-agent action and observation spaces.

NetworkX is a good initial graph travel backend; Shapely is suitable for 2-D regions and obstacle geometry. Both should sit behind interfaces so large-scale or physics backends can replace them.

## Baseline algorithms to make scenarios scientifically useful

The first release should implement or wrap:

- random feasible assignment;
- greedy minimum-cost or maximum-marginal-utility coalition selection;
- exact enumeration for tiny cases;
- set-partitioning/MILP for static small cases;
- earliest-deadline-first with a coalition constructor for CFSTP;
- a one-step look-ahead CFSTP heuristic; and
- an auction protocol with explicit message accounting.

Later baselines can add distributed constraint optimization, merge-and-split, genetic/evolutionary methods, and MARL. Every heuristic should be compared against an independent feasibility checker; small cases should additionally report optimality gap.

## Metrics

Avoid collapsing all results into one score. At minimum, report:

- task success count and weighted reward;
- deadline miss count and lateness;
- makespan, service time, travel time, distance, and waiting time;
- coalition size, churn, formation latency, and unused/redundant capability;
- computation wall time and anytime solution trace;
- messages, bytes, and communication rounds;
- energy/resource consumption;
- allocation feasibility and execution constraint violations;
- robot utilization and workload balance;
- robustness under failure, noise, or packet loss; and
- optimality gap where an oracle is available.

Domain metrics should remain separate: civilians rescued, fires extinguished, object delivery accuracy, surveillance coverage, and so on.

## Visualization acceptance criteria

Every scenario should generate the same families of visual artifacts from its trace:

- a spatial frame with robot identity/type, coalition color, task state, routes, and task progress/deadline cues;
- a robot-by-time Gantt chart showing travel, wait, work, failure, and reassignment;
- a coalition membership timeline showing formation, merge/split, and disband events;
- capability supply-versus-demand views for selected coalitions;
- a task dependency graph for precedence/synchronization scenarios;
- communication topology and message events when enabled; and
- a metrics summary suitable for comparing multiple policies and seeds.

Required outputs should include publication-quality PNG plus SVG or PDF, reproducible GIF/MP4 animation, and an optional interactive HTML replay. Renderers consume recorded traces; they never advance the simulation. Use fixed axes and legends across frames, a colorblind-safe palette, persistent robot colors, distinguish coalition membership with more than color alone, and display the seed/configuration hash in metadata.

Matplotlib directly supports saving animations through FFmpeg or Pillow writers; Plotly is a reasonable optional interactive renderer. Headless batch rendering must be a first-class path.

## Reproducibility and validation

- One root seed produces named child random streams for scenario generation, dynamics, observations, communication, and policy randomness.
- Save the resolved configuration, seed manifest, environment version, policy version, event trace, and summary metrics for every run.
- Validate scenario feasibility at load time where possible.
- Enforce no double-booking for ST robots, capability sufficiency, release/deadline rules, synchronization, resource conservation, and dependency constraints in the kernel.
- Build tiny hand-solvable cases and brute-force oracles before large benchmarks.
- Keep a separate trace auditor that reconstructs results without trusting policy-reported metrics.
- Test equivalent analytical and kinematic cases for agreement when collision/geometry effects are disabled.

## Recommended implementation order

### Milestone 1: research-grade vertical slice

- typed core model and deterministic event trace;
- seeded scenario registry;
- `S0/static_capability` and `S2/cfstp_tiny`;
- random, greedy, and exact-enumeration policies;
- independent feasibility auditor;
- spatial plot, Gantt chart, coalition timeline, and GIF;
- CLI for single runs and seeded batches.

### Milestone 2: spatial and temporal breadth

- graph and continuous 2-D travel backends;
- `S1/cooperative_transport` and `S2/cfstp_paper`;
- MILP and EDF/look-ahead baselines;
- publication-quality comparison plots.

### Milestone 3: dynamic/distributed breadth

- partial observations and communication events;
- `S3/robocup_rescue_lite` and `S5/dynamic_incidents`;
- per-robot policy and PettingZoo adapters;
- failures, online arrivals, stochastic execution, and large-scale profiling.

### Milestone 4: overlapping and learned coalitions

- MT robot semantics and overlapping coalitions;
- `S4/scheduled_surveillance`;
- Gymnasium/PettingZoo learning examples and offline dataset export.

## Primary and authoritative sources

1. B. P. Gerkey and M. J. Mataric, “A Formal Analysis and Taxonomy of Task Allocation in Multi-Robot Systems,” *IJRR*, 2004. [Paper](https://cse-robotics.engr.tamu.edu/dshell/cs689/papers/gerkey04formal.pdf)
2. G. A. Korsah, A. Stentz, and M. B. Dias, “A Comprehensive Taxonomy for Multi-Robot Task Allocation,” *IJRR*, 2013. [CMU record](https://publications.ri.cmu.edu/a-comprehensive-taxonomy-for-multi-robot-task-allocation)
3. E. Nunes, M. Manner, H. Mitiche, and M. Gini, “A Taxonomy for Task Allocation Problems with Temporal and Ordering Constraints,” *Robotics and Autonomous Systems*, 2017. [Author-hosted paper](https://www-users.cse.umn.edu/~gini/papers/NunesRAS.pdf)
4. L. Vig and J. A. Adams, “Multi-Robot Coalition Formation,” *IEEE Transactions on Robotics*, 2006. [DOI](https://doi.org/10.1109/TRO.2006.878948)
5. L. E. Parker and F. Tang, “Building Multirobot Coalitions Through Automated Task Solution Synthesis,” *Proceedings of the IEEE*, 2006. [Author-hosted paper](https://web.eecs.utk.edu/~leparker/publications/ProcOfIEEE06.pdf)
6. S. D. Ramchurn, M. Polukarov, A. Farinelli, C. Truong, and N. R. Jennings, “Coalition Formation with Spatial and Temporal Constraints,” AAMAS, 2010. [Proceedings paper](https://www.ifaamas.org/Proceedings/aamas2010/pdf/01%20Full%20Papers/24_04_FP_0509.pdf)
7. L. Capezzuto, D. Tarapore, and S. D. Ramchurn, “Anytime and Efficient Coalition Formation with Spatial and Temporal Constraints,” 2020. [Preprint](https://arxiv.org/abs/2003.13806)
8. L. Capezzuto, D. Tarapore, and S. D. Ramchurn, “Large-scale, Dynamic and Distributed Coalition Formation with Spatial and Temporal Constraints,” 2021. [Preprint](https://arxiv.org/abs/2106.00379) and [archived code](https://doi.org/10.5281/zenodo.4764646)
9. L. Capezzuto, D. Tarapore, and S. D. Ramchurn, “Multi-Agent Routing and Scheduling Through Coalition Formation,” 2021. [Preprint](https://arxiv.org/abs/2105.00451)
10. R. Basso, B. C. da Silva, E. W. Frew, and R. N. Calvo, “Heterogeneous Coalition Formation and Scheduling with Multi-Skilled Robots,” 2023. [Preprint](https://arxiv.org/abs/2306.11936)
11. Y. Rizk, M. Awad, and E. W. Tunstel, “Cooperative Heterogeneous Multi-Robot Systems: A Survey,” *ACM Computing Surveys*, 2019. [Repository copy](https://scholarworks.aub.edu.lb/bitstreams/fd7f5f60-b3e8-4197-949d-1c216afd22df/download)
12. RoboCup Rescue Simulation, “Research.” [Official domain description](https://rescuesim.robocup.org/research/)
13. Farama Foundation, PettingZoo Parallel API. [Official documentation](https://pettingzoo.farama.org/main/api/parallel/)
14. SimPy. [Official documentation](https://simpy.readthedocs.io/en/stable/index.html)
15. Mesa. [Official documentation](https://mesa.readthedocs.io/stable/index.html)
16. Matplotlib animation. [Official documentation](https://matplotlib.org/stable/api/animation_api.html)
17. NetworkX shortest paths. [Official documentation](https://networkx.org/documentation/stable/reference/algorithms/shortest_paths.html)
18. Shapely. [Official documentation](https://shapely.readthedocs.io/en/stable/manual.html)

## Research caveats

- “Canonical” here means recurring, foundational, or explicitly benchmarked in the coalition/MRTA literature; it does not mean that the field has ratified this exact suite.
- The London Fire Brigade benchmark is a useful external adapter, but its data license and current download path must be checked before vendoring any records.
- The full RoboCup Rescue simulator is much broader than coalition formation. The proposed lite scenario deliberately isolates coalition-relevant mechanisms and should be labeled as an abstraction, not a compliant reproduction.
- Cooperative manipulation can eventually justify a physics backend, but adding contact physics to the first kernel would make allocation algorithms slower and harder to validate without improving the foundational coalition benchmarks.
