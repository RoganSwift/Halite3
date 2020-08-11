# Python 3.6
# rules: https://web.archive.org/web/20181019011459/http://www.halite.io/learn-programming-challenge/game-overview

import sys
import json

# Import the Halite SDK, which will let you interact with the game.
import hlt

# This library contains constant values.
from hlt import constants

# This library contains direction metadata to better interface with the game.
from hlt.positionals import Direction, Position
import logging

""" <<<Game Begin>>> """

# This game object contains the initial game state.
game = hlt.Game()
# At this point "game" variable is populated with initial map data.
# This is a good place to do computationally expensive start-up pre-processing.

logging_level = int(sys.argv[1])

if logging_level >= 1:
#    game.update_frame()
    game_map = game.game_map
    map_array = [
                 [game_map[Position(x,y)].halite_amount for x in range(game_map.width)] for y in range(game_map.height)
                 ]
    logging.info(f"##FL-Map:{str(json.dumps(map_array))}")

# This is the list of personality parameters to be determined through machine learning.
p = [0.5,
     0.5,
     0.5
] #TODO: Consider adding p[3] = cap on last round to make ships

i = 0
for arg in sys.argv[2:]:
    logging.info(f"Arg: {str(arg)}")
    p[i] = float(arg)
    i += 1

q = (p[0]*200, # 0 to 200 - Amount of halite in cell where ships consider it depleted.
     (0.5+p[1]*0.25)*constants.MAX_HALITE, # 50% to 75% of MAX_HALITE - amount of cargo above which ships believe they're returning cargo.
     1 + round(p[2]*29) # 1 to 30 - max number of bots
)

# As soon as you call "ready" function below, the 2 second per turn timer will start.
game.ready("MyPythonBot")

# Now that your bot is initialized, save a message to yourself in the log file with some important information.
#   Here, you log here your id, which you can always fetch from the game object by using my_id.
if logging_level >= 1:
    logging.info("Successfully created bot! My Player ID is {}.".format(game.my_id))

""" <<<Game Loop>>> """

def spiral_walk(starting_x, starting_y):
    if logging_level >= 3:
        logging.info(f"Walking a spiral from {starting_x},{starting_y}.")
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

def dist_betw_positions(position, target, offset_x = 0, offset_y = 0):
    return (position.x+offset_x-target.x)**2+(position.y+offset_y-target.y)**2

def offset_not_in_invalid(position, invalid_positions, offset_x=0, offset_y=0):
    if logging_level >= 3:
        logging.info(f"Offset_not_in_invalid: Position - {str(position)}")
    for invalid in invalid_positions:
        if logging_level >= 3:
            logging.info(f"Offset_not_in_invalid: Invalid - {str(invalid)}")
        if position.x+offset_x == invalid.x and position.y+offset_y == invalid.y:
            if logging_level >= 3:
                logging.info(f"Offset_not_in_invalid: UNSAFE MOVE - REJECT")
            return False
    if logging_level >= 3:
        logging.info(f"Offset_not_in_invalid: SAFE MOVE - ALLOW")
    return True

def determine_target(ship):
    # If ship is full or (ship is on a drained square and carrying lots of halite)
    if ship.halite_amount == constants.MAX_HALITE or (ship.halite_amount > q[1] and game_map[ship.position].halite_amount < q[0]):
        if logging_level >= 3:
                logging.info(f"- - Target for ship {ship.id} is shipyard.")
        return me.shipyard.position
    else:
        logging.info("TEST - Starting search")
        cells_searched = 0
        for search_position in spiral_walk(ship.position.x, ship.position.y):
            if logging_level >= 3:
                logging.info(f"- - - Checking search position {str(search_position)} with {game_map[search_position].halite_amount} halite. ")
            if game_map[search_position].halite_amount >= q[0]:
                if logging_level >= 3:
                    logging.info(f"- - - Target for ship {ship.id} is {str(search_position)}")
                return search_position

            # If there is insufficient halite on the map (very high threshold for depleted), stop.
            cells_searched += 1
            if cells_searched > 4*max(constants.WIDTH, constants.HEIGHT)**2: # this is worst-case of sitting in a corner
                if logging_level >= 1:
                    logging.info(f"??? Search found insufficient halite on map - ordering ship not to move.")
                return ship.position    

def desired_move(ship, invalid_positions=[], on_shipyard=False):
    if logging_level >= 3:
        logging.info(f"Invalid Positions: {str(invalid_positions)}")
    if logging_level >= 2:
        logging.info("- Checking desired move for ship {}.".format(ship.id))
    position = ship.position
    target = determine_target(ship)

    if ship.halite_amount < game_map[ship.position].halite_amount*0.1 or position == target:
        return ("stay", position)

    if logging_level >= 2:
        logging.info(f"- - Desired move for ship {ship.id} is {str(target)}.")
    move_order = "stay"
    destination = position
    if on_shipyard:
        best_distance = 1000 # insist that ships move off the shipyard unless impossible
    else:
        best_distance = dist_betw_positions(position, target)

    options = ((Direction.North, 0,-1),
               (Direction.East, 1,0),
               (Direction.South, 0,1),
               (Direction.West, -1,0))
    for order, offset_x, offset_y in options:
        diagonal_distance = dist_betw_positions(position, target, offset_x, offset_y)
        if diagonal_distance < best_distance and offset_not_in_invalid(position, invalid_positions, offset_x, offset_y):
            move_order = order
            destination = Position(position.x+offset_x, position.y+offset_y)
            best_distance = diagonal_distance

    if logging_level >= 2:
        logging.info(f"- - Next step for ship {ship.id} is {str(move_order)} to {str(destination)}")        
    return (move_order, destination)

def move_ship_recursive(ship, invalid_positions, ignore_ships, moved_ships):
    # Orders closest-to-target move for ship and any ship in its path, recursively.
    moved = False
    loopcounter = 0 # Infinite loops terrify me, so loopcounter has a max of 10, which should never occur. (Actual max 5)
    while not moved and loopcounter < 10:
        # Check for the ship's desired move, considering that it can't go to any committed positions (invalid_positions)
        move_direction, move_position = desired_move(ship, invalid_positions, ship.position == me.shipyard.position)

        # Collisions are only possible with ships meeting the following criteria:
        # (1) has not moved yet and (2) is currently on the target space
        #  - Ships after this ship won't target this target because it will be in invalid_targets once this ship commits
        #  - and this ship couldn't have targeted this space if another ship committed to staying still in it.
        # (3) is not higher in the recursive chain than this ship
        #  - you know any ship higher up the chain wants to move from its spot
        # To resolve this, check every ship for these three criteria
        no_ships_on_target = True
        for other_ship in me.get_ships():
            if other_ship.position == move_position and other_ship.id not in ignore_ships and other_ship.id not in moved_ships:
                # If one is found, let it move first, ignoring this ship (criteria (3) above)
                move_ship_recursive(other_ship, invalid_positions, [iship for iship in ignore_ships].append(ship.id), moved_ships)
                # If that ship (or its down-chain friends) decided to commit this spot,
                #   we need to restart the while loop and desired_move elsewhere.
                if move_position in invalid_positions:
                    no_ships_on_target = False
                    break

        # If, after looking at all other ships, none meet the criteria and want to stay, we can commit the move.
        if no_ships_on_target:
            if move_direction == "stay":
                command_queue.append(ship.stay_still())
                invalid_positions.append(ship.position)
            else:
                command_queue.append(ship.move(move_direction)) 
                invalid_positions.append(move_position)
            moved_ships.append(ship.id)
            moved = True
        
        loopcounter += 1
    
    # As above, if the while loop goes way beyond where it should, fail gracefully and log.
    if not moved:
        logging.info(f"FLWarning:Ship {ship.id} could not find a target in 10 checks")
        command_queue.append(ship.stay_still())
        invalid_positions.append(ship.position)

while True:
    if logging_level >= 1:
        logging.info(f"##FL-Round:{game.turn_number}:{game.me.halite_amount}")

    game.update_frame() # pull updated data
    me = game.me # player data
    game_map = game.game_map # updated game map
    command_queue = [] # command queue ready to be populated

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
            move_ship_recursive(ship, invalid_positions, ignore_ships, moved_ships)

    logging.info(f"Command queue: {str(command_queue)}")

    if me.halite_amount >= constants.SHIP_COST and not me.shipyard.position in invalid_positions and len(me.get_ships()) <= q[2]:
        if logging_level >= 2:
                logging.info("Generating new ship.")
        command_queue.append(me.shipyard.spawn())

    # Send your moves back to the game environment, ending this turn.
    game.end_turn(command_queue)

