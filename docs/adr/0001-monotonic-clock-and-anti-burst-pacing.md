# 0001: Monotonic Clock Pacing and Anti-Burst Protection

To prevent location-based games (such as Pokémon GO and Pikmin Bloom) from detecting abnormal GPS update spikes or teleportation jumps, all coordinate simulation dispatches—both from backend Auto Navigation and frontend Keyboard Manual Steering—are strictly paced to a minimum interval of 1.0 second using monotonic clocks. When thread execution or browser timers lag, excess catch-up ticks are dropped rather than burst-dispatched or fast-forwarded across large distances, preserving realistic physical movement step sizes.

## Considered Options

1. **Instant keydown dispatch without pacing**: Rejected because rapid key taps produce GPS injection rates > 1Hz, tripping anti-cheat heuristics.
2. **Lag compensation via distance fast-forwarding**: Rejected because thread delays or system sleep would trigger sudden large distance leaps upon resume, appearing as unnatural speed surges.
3. **Paced monotonic dispatch with dropped lag ticks**: Accepted because it enforces steady 1Hz cadence and deterministic per-second step distances (`speed_kmh / 3.6` meters) under all scheduling conditions.
