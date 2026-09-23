"""Survey every wall encountered on a run, using a generous default hop
(20 frames) to get past each one and keep exploring -- finds where a
4-tile wall actually is, so tune_climb_height.py's sweep can be pointed at
it directly, instead of guessing."""
import sys, os
os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.path.insert(0, ".")
import setuptools
import gym_super_mario_bros
from nes_py.wrappers import JoypadSpace
from mario.ram import tile_ram
from run_mario import ADDR_ENEMY_X, ADDR_ENEMY_ACTIVE, N_ENEMY_SLOTS, ADDR_MARIO_X
from tune_climb_height import contiguous_height

MOVES = [["right", "B"], ["right", "A", "B"]]
RUN, JUMP = 0, 1

env = gym_super_mario_bros.make("SuperMarioBros-1-1-v0")
env = JoypadSpace(env, MOVES)
obs = env.reset()
ram = env.unwrapped.ram
hop = 0
walls_seen = set()
for frame in range(3000):
    if hop == 0 and tile_ram.solid_ahead(ram):
        col0 = tile_ram._mario_abs_col(ram)
        buf1, buf2 = tile_ram._grids(ram)
        h = contiguous_height(buf1, buf2, col0 + 1)
        if col0 not in walls_seen:
            walls_seen.add(col0)
            print(f"frame {frame}: wall at col={col0+1}, height={h} tiles")
        hop = 25 if h >= 3 else 15
    mario_x = int(ram[ADDR_MARIO_X])
    if hop == 0:
        for i in range(N_ENEMY_SLOTS):
            if ram[ADDR_ENEMY_ACTIVE + i] and 0 < int(ram[ADDR_ENEMY_X + i]) - mario_x < 24:
                hop = 20
                break
    action = JUMP if hop > 0 else RUN
    if hop > 0:
        hop -= 1
    obs, r, done, info = env.step(action)
    if done:
        print(f"died at frame {frame}")
        break
