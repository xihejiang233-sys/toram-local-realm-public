# Encounter scheduler / 野王调度示例

这是独立编写的内存调度示例，仅演示野王的首次生成、击败、清除和冷却。所有标识和测试时间均为虚构。它不是完整的本地服，不能连接官方客户端。

This standalone, in-memory example schedules field boss encounters. Every identifier and test interval is fictional. It is not a complete game server and cannot connect to an official client.

## 行为 / Behavior

- 进入有规则的场景时，每位玩家独立获得首次生成事件。重复进图或重复请求不会额外生成。切换场景会保留原场景的状态。
- 打败当前代的实体后，尸体会阻止刷新。清除尸体时开始冷却。到期后，玩家仍在场且已脱战，下一次调度检查就会生成一只。已离场时不会收到生成事件。
- A pool belongs to one player in one scene. The first eligible entry emits a spawn. Repeated entries, explicit requests and ticks share one creation decision.
- Defeat leaves a corpse. Clearing it starts the cooldown. While the player is present and out of combat, the first tick at or after the deadline emits the next generation. Stale defeat and clear events cannot change a newer generation.

## 离线运行 / Run offline

需要 Python 3.10 或更新版本，仅使用标准库。在本目录执行以下命令。Requires Python 3.10 or newer and only the standard library. From this directory, run

```sh
python -B -m unittest -v
```

测试用模拟时钟推进到冷却边界，无需实际等待。示例中的 7 秒和 11 秒是两条合成测试规则。调度器由调用方周期性调用 `tick()` 驱动，直接返回新的生成事件；重复进入已存在活体的场景时不会重发生成事件。所有状态只存在于当前对象的内存中。

The tests advance a fake clock to exercise both sides of each deadline without sleeping. Seven and eleven seconds are fixture values. A caller drives the scheduler by calling `tick()` periodically and consuming the returned spawn events. Entering a scene with an existing live encounter does not replay its spawn. State lasts for the lifetime of the scheduler object.
