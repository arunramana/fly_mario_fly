"""REFACTOR_PLAN.md phase 5: proves sim.episode.Episode actually works
end-to-end with a real Policy (bridge.policy.JumpPolicy) and a real
Environment (mario.emulator.environment.MarioEnvironment) -- not a toy
pair. Not claiming to reproduce any golden run: JumpPolicy is genuinely
narrower than run_steering.main()'s full system (no steering, terrain,
mushroom body, habituation, or MDN) -- see bridge/policy.py's own
docstring for the scoping. This test is about the LOOP composing
correctly (Policy/Environment/observers wired together, seeded reset,
early stop on death), not about matching a specific trajectory.
"""
from __future__ import annotations

from bridge.policy import JumpPolicy
from mario.emulator.environment import MarioEnvironment
from sim.episode import Episode


class _RecordingObserver:
    def __init__(self):
        self.steps = []
        self.ended_at = None

    def on_step(self, step, observation, action):
        self.steps.append((step, action))

    def on_episode_end(self, steps):
        self.ended_at = steps


def test_episode_runs_a_real_policy_against_a_real_environment():
    policy = JumpPolicy()
    env = MarioEnvironment(level="1-1")
    observer = _RecordingObserver()
    episode = Episode(policy, env, observers=[observer])

    final_observation = episode.run(seed=0, max_steps=300)

    assert len(observer.steps) > 0
    assert observer.ended_at == len(observer.steps)
    # every action is a valid MOVES index (mario.actions.actions, 8-way)
    assert all(0 <= action <= 7 for _, action in observer.steps)
    assert hasattr(final_observation, "ram") and hasattr(final_observation, "done")
    env.close()


def test_episode_stops_early_on_done():
    """The early-stop mechanism itself, checked against a small, fast,
    deterministic fake environment/policy -- not a real bot's unpredictable
    survival. (A real JumpPolicy episode was tried here first: over 5000
    frames on 1-1 it neither died nor flagged -- no climb reflex means it
    can get stuck bouncing against an obstacle indefinitely, a real and
    plausible outcome for a policy this narrow, not a bug. See bridge/
    policy.py's own docstring: JumpPolicy is deliberately not the full
    system.)"""

    class _CountingPolicy:
        def reset(self, seed):
            pass

        def act(self, observation):
            return 0

    class _Obs:
        def __init__(self, step, done):
            self.step, self.done = step, done

    class _DoneAtStepThree:
        def __init__(self):
            self._step = 0

        def reset(self, seed):
            self._step = 0
            return _Obs(0, done=False)

        def step(self, action):
            self._step += 1
            return _Obs(self._step, done=(self._step >= 3))

    observer = _RecordingObserver()
    episode = Episode(_CountingPolicy(), _DoneAtStepThree(), observers=[observer])
    final_observation = episode.run(seed=0, max_steps=100)

    assert final_observation.done is True
    assert final_observation.step == 3
    assert len(observer.steps) == 3  # stopped at step 3, not run to max_steps=100
    assert observer.ended_at == 3


def test_episode_reset_is_seed_independent_given_no_noise():
    """JumpPolicy draws no randomness (sigma is not modelled here) -- two
    runs from the same policy/environment pair should behave identically
    regardless of which seed is passed, the same determinism property
    tests/golden/ relies on for the full system at sigma=0."""
    policy = JumpPolicy()
    env = MarioEnvironment(level="1-1")
    observer_a = _RecordingObserver()
    Episode(policy, env, observers=[observer_a]).run(seed=1, max_steps=200)
    env.close()

    policy_b = JumpPolicy()
    env_b = MarioEnvironment(level="1-1")
    observer_b = _RecordingObserver()
    Episode(policy_b, env_b, observers=[observer_b]).run(seed=99, max_steps=200)
    env_b.close()

    assert [a for _, a in observer_a.steps] == [a for _, a in observer_b.steps]
