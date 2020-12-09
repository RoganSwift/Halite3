# Python 3.6
# rules: https://web.archive.org/web/20181019011459/http://www.halite.io/learn-programming-challenge/game-overview

""" Stage 0: Imports - Permitted X minutes here
    Access to only code.    
"""

import sys
import json
import logging

# Import the Halite SDK, which will let you interact with the game.
import hlt
from hlt import constants # This library contains constant values.
from hlt.positionals import Direction, Position # This library contains direction metadata to better interface with the game.

#sys.argv[0] is "MyBot.py", which we don't need to save.
if len(sys.argv) >= 2:
    logging_level = int(sys.argv[1])
else:
    logging_level = 0

# TODO: pickle_level as arg[2] removed. See if you can shift stuff up.

# This is the list of personality parameters to be determined through machine learning.
p = [0.5,
     0.5,
     0.5
] #TODO: Consider adding p[3] = cap on last round to make ships
#TODO: Add halite depleted on turn 400; linear interpolation between two

i = 0
for arg in sys.argv[3:]:
    sc_log(1, f"Arg: {str(arg)}")
    p[i] = float(arg)
    i += 1

def sc_log(level, message):
    '''Shortcut Log: if logging_level >= level: logging.info(message)'''
    if logging_level >= level:
        logging.info(message)

def spiral_walk(starting_x, starting_y):
    '''Spiral walk iterator: yield a position in the square spiral starting at x,y, walking x+1 and turning towards y-1'''
    sc_log(3, f"Walking a spiral from {starting_x},{starting_y}.")
    x,y = starting_x, starting_y
    yield Position(x,y)
    i = 1
    while True:
        for _ in range(i):
            x+=1
        yield Position(x,y)
        for _ in range(i):
            y-=1
            yield Position(x,y)
        i+=1
        for _ in range(i):
            x-=1
            yield Position(x,y)
        for _ in range(i):
            y+=1
            yield Position(x,y)
        i+=1

def dist_betw_positions(start, end):
    '''return (start.x-end.x)**2+(start.y-end.y)**2'''
    return (start.x-end.x)**2+(start.y-end.y)**2

def determine_target(ship, game_map, shipyard_position):
    # If ship is full or (ship is on a drained square and carrying lots of halite)
    if ship.halite_amount == constants.MAX_HALITE or (ship.halite_amount > q[1] and game_map[ship.position].halite_amount < q[0]):
        sc_log(3, f"- - Target for ship {ship.id} is shipyard.")
        return shipyard_position
    else:
        cells_searched = 0
        for search_position in spiral_walk(ship.position.x, ship.position.y):
            sc_log(3, f"- - - Checking search position {str(search_position)} with {game_map[search_position].halite_amount} halite.")
            if game_map[search_position].halite_amount >= q[0]:
                sc_log(3, f"- - - Target for ship {ship.id} is {str(search_position)}")
                return search_position

            # If there is insufficient halite on the map (very high threshold for depleted), stop.
            cells_searched += 1
            if cells_searched > 4*max(constants.WIDTH, constants.HEIGHT)**2: # this is worst-case of sitting in a corner
                sc_log(1, f"??? Search found insufficient halite on map - ordering ship not to move.")
                return ship.position    

def desired_move(ship, invalid_positions, shipyard_position):
    on_shipyard = (shipyard_position == ship.position)
    sc_log(3, f"Invalid Positions: {str(invalid_positions)}")
    sc_log(2, "- Checking desired move for ship {}.".format(ship.id))
    position = ship.position
    target = determine_target(ship, shipyard_position)

    if ship.halite_amount < game_map[ship.position].halite_amount*0.1 or position == target:
        return ("stay", position)

    sc_log(2, f"- - Desired move for ship {ship.id} is {str(target)}.")
    move_order = "stay"
    destination = position
    if on_shipyard:
        best_distance = 1000 # insist that ships move off the shipyard unless impossible
    else:
        best_distance = dist_betw_positions(position, target)

    options = [Direction.North, Direction.South, Direction.East, Direction.West]

    for option in options:
        diagonal_distance = dist_betw_positions(position + option, target)
        if diagonal_distance < best_distance and position + option not in invalid_positions:
            move_order = option
            destination = position + option
            best_distance = diagonal_distance

    sc_log(2, f"- - Next step for ship {ship.id} is {str(move_order)} to {str(destination)}")        
    return (move_order, destination)

def move_ship_recursive(ship, invalid_positions, ignore_ships, moved_ships, me):
    sc_log(1, f"Move_ship_recursion start: Ship {ship.id}")
    # Orders closest-to-target move for ship and any ship in its path, recursively.
    moved = False
    loopcounter = 0 # Infinite loops terrify me, so loopcounter has a max of 10, which should never occur. (Actual max 5)
    while not moved and loopcounter < 10:
        # Check for the ship's desired move, considering that it can't go to any committed positions (invalid_positions)
        move_direction, move_position = desired_move(ship, invalid_positions, ship.position == me.shipyard.position)
        sc_log(1, "Move_ship_recursion: Ship {ship.id} considering direction {move_direction} position {move_position}")
        # Collisions are only possible with ships meeting the following criteria:
        # (1) has not moved yet and (2) is currently on the target space
        #  - Ships after this ship won't target this target because it will be in invalid_targets once this ship commits
        #  - and this ship couldn't have targeted this space if another ship committed to staying still in it.
        # (3) is not higher in the recursive chain than this ship
        #  - you know any ship higher up the chain wants to move from its spot
        # To resolve this, check every ship for these three criteria
        no_ships_on_target = True
        for other_ship in me.get_ships():
            if ship.id != other_ship.id and other_ship.position == move_position and other_ship.id not in ignore_ships and other_ship.id not in moved_ships:
                sc_log(1, f"Move_ship_recursion: Ship {ship.id} blocked by {other_ship}. Letting it go first.")
                # If one is found, let it move first, ignoring this ship (criteria (3) above)
                move_ship_recursive(other_ship, invalid_positions, [iship for iship in ignore_ships].append(ship.id), moved_ships, me)
                # If that ship (or its down-chain friends) decided to commit this spot,
                #   we need to restart the while loop and desired_move elsewhere.
                if move_position in invalid_positions:
                    no_ships_on_target = False
                    break

        # If, after looking at all other ships, none meet the criteria and want to stay, we can commit the move.
        if no_ships_on_target:
            if move_direction == "stay":
                sc_log(1, f"Move_ship_recursion: Ship {ship.id} decided to stay at {ship.position}")
                command_queue.append(ship.stay_still())
                invalid_positions.append(ship.position)
            else:
                sc_log(1, f"Move_ship_recursion: Ship {ship.id} decided to move {move_direction} to {move_position}")
                command_queue.append(ship.move(move_direction)) 
                invalid_positions.append(move_position)
            moved_ships.append(ship.id)
            moved = True
        
        loopcounter += 1
    
    # As above, if the while loop goes way beyond where it should, fail gracefully and log.
    if not moved:
        sc_log(1, f"FLWarning:Ship {ship.id} could not find a target in 10 checks")
        command_queue.append(ship.stay_still())
        invalid_positions.append(ship.position)

def one_game_step(game):
    """Determine and return the command_queue actions to take this turn."""
    me = game.me
    game_map = game.game_map
    command_queue = [] # command queue ready to be populated

    sc_log(1, f"##FL-Round:{game.turn_number}:{game.me.halite_amount}")

    #TODO: Create a function which (game_map, ship_positions) -> command_queue. Allows testing + replay

    #Create list of committed destinations (moving here causes a collision)
    invalid_positions = [] #TODO: Rename invalid_positions to committed_positions?
    ignore_ships = []
    moved_ships = []
    #TODO: Consider re-implementing moved_ships as ships_to_move = [ship for ship in me.get_ships()],
    #      including removing ships as ships are moved in move_ship_recursive and
    #      replacing the below for loop with while len(ships_to_move)>0: move_ship_recursive(ships_to_move[0])

    #TODO: Consider enemy positions when choosing to move
    #      If you can't grab a list of their positions, spiral_walk until you find the closest.
    for ship in me.get_ships():
        if ship.id not in moved_ships:
            move_ship_recursive(ship, invalid_positions, ignore_ships, moved_ships, me)

    if me.halite_amount >= constants.SHIP_COST and not me.shipyard.position in invalid_positions and len(me.get_ships()) <= q[2]:
        sc_log(2, "Generating new ship.")
        command_queue.append(me.shipyard.spawn())

    sc_log(1, f"Command queue: {str(command_queue)}")
    return command_queue

""" Stage 1: Pre-game scanning - Permitted X minutes here.
    Once game = hlt.Game() is run, you have access to the game map for computationally-intensive start-up pre-processing.
"""
game = hlt.Game()

if logging_level >= 1:
#    game.update_frame()
    game_map = game.game_map
    map_array = [
                 [game_map[Position(x,y)].halite_amount for x in range(game_map.width)] for y in range(game_map.height)
                 ]
    sc_log(1, f"##FL-Map:{str(json.dumps(map_array))}")

# Apply loaded personality parameters

q = (p[0]*200, # 0 to 200 - Amount of halite in cell where ships consider it depleted.
     (0.5+p[1]*0.25)*constants.MAX_HALITE, # 50% to 75% of MAX_HALITE - amount of cargo above which ships believe they're returning cargo.
     1 + round(p[2]*29) # 1 to 30 - max number of bots
)

""" Stage 2: Game Turns - Permitted 2 seconds per turn.
    Once game.ready("MyPythonBot") is run, you have access to positions of units and the ability to send commands.
"""
game.ready("MyPythonBot")
sc_log(1, "Successfully created bot! My Player ID is {}.".format(game.my_id))

while True:
    game.update_frame() # pull updated data
    command_queue = one_game_step(game)
    game.end_turn(command_queue)
# TODO: Anything in a function is not visible to other functions unless passed, so me/game_map/invalid_positions all behave wrong now that I've moved them into a function
