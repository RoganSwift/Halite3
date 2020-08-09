import os
#https://cmdlinetips.com/2014/03/how-to-run-a-shell-command-from-python-and-get-the-output/
import subprocess
#https://stackoverflow.com/questions/4760215/running-shell-command-and-capturing-the-output
import json
from statistics import stdev, mean
import itertools
import matplotlib.pyplot as plt
import time

def call_halite(width=32, height=32, bot1="MyBot.py 2", bot2="MyBot.py 0", replaying=False, delete_logs=True):
    if replaying:
        replay_text = ""
    else:
        replay_text = "--no-replay"

    command = f'halite.exe -i replays --no-logs {replay_text} --width {width} --height {height} "python {bot1}" "python {bot2}"'

    executed = subprocess.run(command, stderr=subprocess.PIPE, universal_newlines=True, shell=True)
    
    collisions = 0
    for line in executed.stderr.split("\n"):
        if line.find("[info] Map seed is") >= 0:
            seed_string = line[18:]
            seed = int(seed_string)
        if line.find("[P0]") >= 0 and line.find("collided") >= 0:
            collisions += 1

    halite_amounts = []
    with open("bot-0.log") as log_file:
        for line in log_file:
            if line.find("##FL-Map") >= 0:
                game_map_string = line.split(":")[3]
                game_map = json.loads(game_map_string)
            if line.find("##FL-Round") >= 0:
                halite_amount_strings = line.split(":")
                halite_amounts.append([int(halite_amount_strings[3]),int(halite_amount_strings[4])])
    if delete_logs:    
        os.remove("bot-0.log")
        os.remove("bot-1.log")

    return {'map':game_map,'halite':halite_amounts, 'seed':seed, 'collisions':collisions}

def scan_pvalues(repeats=5, *args):
    p_values = args
    averages = []
    for sample in itertools.product(*p_values): 
        maxes = []
        str_sample = ' '.join([str(item) for item in sample])
        print(f"Calling Halite with p values: {str(sample)}")
        for _ in range(repeats):
            data = call_halite(bot1=f"MyBot.py 2 {str_sample}", delete_logs=False)
            halite_data = data['halite']
            max_round, max_halite = sorted(halite_data,key=lambda x:x[1], reverse=True)[0]
            print(f" - Best halite was {max_halite} on round {max_round}")

            maxes.append(max_halite)
        averages.append([round(mean(maxes)), *sample])

    return averages

P0_values = P1_values = P2_values = [0.1, 0.3, 0.5, 0.7, 0.9]

before = time.time()
averages = scan_pvalues(1, P0_values, P1_values, P2_values)
after = time.time()

sorted_averages = sorted(averages,key=lambda x: x[0],reverse=True)
pretty_sorted_averages = "\n".join([str(row) for row in sorted_averages])

with open("result.log", "w") as file:
    file.write(f"Time elapsed: {str(round(after-before))} seconds\n")
    file.write(pretty_sorted_averages)

#TODO: Figure out why collisions occur. Watch a replay.