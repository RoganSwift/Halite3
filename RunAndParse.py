import os
#https://cmdlinetips.com/2014/03/how-to-run-a-shell-command-from-python-and-get-the-output/
import subprocess
#https://stackoverflow.com/questions/4760215/running-shell-command-and-capturing-the-output
import json
from statistics import stdev, mean
import itertools
import matplotlib.pyplot as plt
import time
import math
import random
import MyBot
import EGO
import numpy as np

def call_halite(width=32,
                height=32,
                bot1="MyBot.py",
                bot2="EmptyBot.py",
                replaying=False,
                delete_logs=True):
    if replaying:
        replay_text = ""
    else:
        replay_text = "--no-replay"

    location = 'C:\\Users\\Swift-PC\\Desktop\\CodingProjects\\Halite\\'
    command = f'{location}halite.exe -i replays {replay_text} --width {width} --height {height} "python {location}{bot1}" "python {location}{bot2}"'

    executed = subprocess.run(command, stderr=subprocess.PIPE, universal_newlines=True, shell=True)
    
    collisions = 0
    for line in executed.stderr.split("\n"):
        if line.find("[info] Map seed is") >= 0:
            seed_string = line[18:]
            seed = int(seed_string)
        if line.find("[P0]") >= 0 and line.find("collided") >= 0:
            collisions += 1

    halite_amounts = []
    with open(f"bot-0.log", 'r') as log_file:
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

    return {'map':game_map,'halite':halite_amounts, 'seed':seed, 'collisions':collisions, 'stderr':executed.stderr}

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

def many_repeat_n_calls(n,z,p_values):
    p_values_text = ' '.join([str(item) for item in p_values])
    averages = []
    for i in range(z):
        print("Loop {}".format(i))
        maxes = []
        for _ in range(n):
            data = call_halite(bot1=f"MyBot.py 2 {p_values_text}", delete_logs=False)
            halite_data = data['halite']
            _, max_halite = sorted(halite_data,key=lambda x:x[1], reverse=True)[0]
            maxes.append(max_halite)
        print(" - Maxes: {}".format(maxes))
        print(" - Mean: {}".format(mean(maxes)))
        averages.append(mean(maxes))
        print()
    print("Mean of means: {}".format(mean(averages)))
    print("Stdev of means: {}".format(stdev(averages)))
    return (mean(averages),stdev(averages))

def latin_hypercube(n_dimensions):
    '''Produce random sample points within a multi-dimension unit-length hypercube where no two points are orthogonal.''' 
    n_samples = math.ceil(2*math.sqrt(n_dimensions)) # Gotta choose some number for this. Definitely can be improved.
    div_width = 1/n_samples
    # For each dimension (outer for loop), produce one random sample spot in each div_width-spaced bin, then shuffle each dimension's points.
    dimension_points = [random.sample(
                                       [(i+random.random())*div_width for i in range(n_samples)],
                                       n_samples
                                      )
                        for _ in range(n_dimensions)]
    # Produce a list of sample points, with the ith sample point using the ith element of each dimension's points.
    # Since there's only one sample point per bin in each dimension, the result is a latin hypercube.
    sample_points = list(zip(*dimension_points))
    return sample_points

def run_test(state_file_name):
    bot = MyBot.FlinkBot()
    return bot.perform_test(state_file_name)

def optimize():
    with open('Halite\optimize.log','w') as logfile:
        # Setup
        kernel = lambda r: np.exp(-0.5 * r**2)
        predictor = EGO.EGO(3, kernel, 0.1)

        def call_halite_with_parameters(parameters):
            bot_settings = "MyBot.py -p %s" % (" ".join([str(param) for param in parameters]))
            logfile.write(bot_settings+"\n")
            results = call_halite(bot1=bot_settings, delete_logs=False)
            maximum = max([round[1] for round in results['halite']])
            return maximum

        starter_values = latin_hypercube(3)
        #TODO: generates 4 starter values for 3 dimensions

        for value_set in starter_values:
            halite_result = call_halite_with_parameters(value_set)
            print(f"Added point: {value_set} is {halite_result}")
            predictor.add_point(halite_result, value_set)

        one_dim = tuple(range(0, 10, 1))
        sample_points = tuple(itertools.product(one_dim, one_dim, one_dim))
        interp_x = np.asarray(sample_points) / 10 # the positions we predict at

        while True:
            # predict the expected (interp_y) and std.dev. (interp_u) at each in interp_x/
            interp_y, interp_u = predictor.generate_predictions(interp_x)

            max_pos = np.argmax(interp_y+interp_u)
            max_y_u = interp_x[max_pos, :]

            max_pos = np.argmax(interp_u)
            max_u = interp_x[max_pos, :]
            max_u_val = interp_u[max_pos]

            #TODO: It'll re-sample the same point a second time
            #TODO: But the max_u for the point shouldn't be very high
            #result_string = f"Best y+u: {max_y_u}. Sampling at {max_u} to explore ({max_u_val})."
            result_string = f"Best y+u: {max_y_u}."
            print(result_string)
            logfile.write(result_string+"\n")

            # actually calculate the real value associated with the prediction
            halite_result = call_halite_with_parameters(max_y_u)
            result_string = f"Added point: {max_y_u} is {halite_result}"
            print(result_string)
            logfile.write(result_string+"\n")
            predictor.add_point(halite_result, max_y_u)

            # repeat. We know it's "good enough" when the answers converge about some x values.

if __name__ == "__main__":
    optimize()
    #print(run_test("example_state r6.state"))
    # P0_values = P1_values = P2_values = [0.1, 0.3, 0.5, 0.7, 0.9]

    # before = time.time()
    # averages = scan_pvalues(1, P0_values, P1_values, P2_values)
    # after = time.time()

    # sorted_averages = sorted(averages,key=lambda x: x[0],reverse=True)
    # pretty_sorted_averages = "\n".join([str(row) for row in sorted_averages])

    # with open("result.log", "w") as file:
    #     file.write(f"Time elapsed: {str(round(after-before))} seconds\n")
    #     file.write(pretty_sorted_averages)

    #results = call_halite(bot1="MyBot.py -p 0.5 0.5 0.5", delete_logs=False)
    #print(results['stderr'])

    #print(many_repeat_n_calls(1,10,[0.5,0.5,0.5,0.5]))


    #TODO: Figure out why collisions occur. Watch a replay.