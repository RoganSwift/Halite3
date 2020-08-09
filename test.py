import os
#https://cmdlinetips.com/2014/03/how-to-run-a-shell-command-from-python-and-get-the-output/
import subprocess
#https://stackoverflow.com/questions/4760215/running-shell-command-and-capturing-the-output
import json
from statistics import stdev, mean
import itertools

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

    print(executed.stderr)

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

def scan_pvalues(P0_values, P1_values):
    averages = []
    for sample in itertools.product(P0_values, P1_values): 
        maxes = []
        for _ in range(5):
            data = call_halite(bot1=f"MyBot.py 2 {sample[0]} {sample[1]}", delete_logs=False)
            halite_data = data['halite']
            two_columns = zip(*halite_data)
            max_halite = max(list(two_columns)[1])

            maxes.append(max_halite)
        averages.append([sample, mean(maxes)])

    return averages

P0_values = [0.1, 0.5, 0.9]
P1_values = [0.1, 0.5, 0.9]

result = call_halite()
print(f"seed: {result['seed']}, collisions: {result['collisions']}")