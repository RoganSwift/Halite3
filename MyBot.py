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
import random
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
p = [0.05,
     0.5,
     0.5
]

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
    #improvement would be identifying base locations at start-up, then for each base, listing cells with enough halite and removing a cell from the list when it gets low enough. Don't need to search empty fields.
    #can't have station keep track of this instead, as bots might be told to cross long distance to find closest halite, which is opposite of desired.

def dist_betw_positions(position,target,offset_x = 0, offset_y = 0):
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
            if cells_searched > constants.WIDTH*constants.HEIGHT:
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
        best_distance = 1000 # insist that ships move off the shipyard
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

def move_ship(ship, invalid_positions, ignore_ships):
    #TODO: Add comments
    moved = False
    loopcounter = 0
    while not moved and loopcounter < 100:
        if ship.position == me.shipyard.position:
            on_shipyard = True
        else:
            on_shipyard = False
        move_direction, move_position = desired_move(ship, invalid_positions, on_shipyard)

        for other_ship in me.get_ships():
            if other_ship.position == move_position and other_ship not in ignore_ships:
                move_ship(other_ship, invalid_positions, [iship for iship in ignore_ships].append(ship))
            else:
                if move_direction == "stay":
                    command_queue.append(ship.stay_still())
                    invalid_positions.append(ship.position)
                else:
                    command_queue.append(ship.move(move_direction)) 
                    invalid_positions.append(move_position)
                moved = True
        
        loopcounter += 1
    
    if loopcounter >= 100:
        command_queue.append(ship.stay_still())
        invalid_positions.append(ship.position)


while True:
    if logging_level >= 1:
        logging.info(f"##FL-Round:{game.turn_number}:{game.me.halite_amount}")

    # This loop handles each turn of the game. The game object changes every turn, and you refresh that state by
    #   running update_frame().
    game.update_frame()
    # You extract player metadata and the updated map metadata here for convenience.
    me = game.me
    game_map = game.game_map

    # A command queue holds all the commands you will run this turn. You build this list up and submit it at the
    #   end of the turn.
    command_queue = []
    #Create list of committed destinations (moving here causes a collision)
    invalid_positions = []
    ignore_ships = []

    #TODO: for ship in ships, if ship not in command_queue: move_ship()






    a = '''
    # Possible collision case:
    #   s
    # >>>s
    #   s
    # If 2 > bots move before 3rd > bot, 3rd bot has no place to go.




    #Create list of ships that have received orders from the first step.
    #TODO: Sometimes bots collide.
    #TODO: Watch a replay. See what the bots do.
    ordered_ships = []

    # If ship cannot move due to insufficient halite, order to stay.
    # This must be done first so that staying still is always an option.
    if logging_level >= 2:
        logging.info("First orders - still ships.")

    for ship in me.get_ships():
        if ship.halite_amount < game_map[ship.position].halite_amount*0.1 or ship.position == determine_target(ship):
            if logging_level >= 2:
                logging.info(f"!!! Ordering ship {ship.id} to remain in place.")

            command_queue.append(ship.stay_still())
            if logging_level >= 3:
                logging.info(f" - Adding to invalid_positions {str(ship.position)}") 
            invalid_positions.append(ship.position)
            ordered_ships.append(ship)

    if logging_level >= 2:
        logging.info(f"- Invalid positions are {str(invalid_positions)}")    

    #Make a list of each bot's id, desired movement w/o consideration of collisions, and destination
    ship_orders = [[ship, *desired_move(ship)] for ship in me.get_ships()]
    
    if logging_level >= 2:
        logging.info("Second orders - All ships")

    # For all other ships (else below)
    for i in range(len(ship_orders)):
        if ship_orders[i][0] in ordered_ships:
            if logging_level >= 2:
                logging.info(f"- Ship {ship_orders[i][0].id} still remaining in place.")
            pass
        else:
            if logging_level >= 2:
                logging.info(f"- Preparing to order ship {ship_orders[i][0].id}.")

            if ship_orders[i][0].position == me.shipyard.position:
                on_shipyard = True
            else:
                on_shipyard = False
            move_direction, move_position = desired_move(ship_orders[i][0], invalid_positions, on_shipyard)
            if move_direction == "stay":
                if logging_level >= 2:
                    logging.info(f"!!! Ordering ship {ship_orders[i][0].id} to stay still.")
                command_queue.append(ship_orders[i][0].stay_still())
            else:
                if logging_level >= 2:
                    logging.info(f"!!! Ordering ship {ship_orders[i][0].id} to move {str(move_direction)}.")
                command_queue.append(ship_orders[i][0].move(move_direction))
            invalid_positions.append(move_position)   
'''


    # If the game is in the first 200 turns and you have enough halite, spawn a ship.
    # Don't spawn a ship if you currently have a ship at port, though - the ships will collide.
    if game.turn_number <= 200 and me.halite_amount >= constants.SHIP_COST and not game_map[me.shipyard].is_occupied and len(me.get_ships()) <= q[2]:
        if logging_level >= 2:
                logging.info("Generating new ship.")
        command_queue.append(me.shipyard.spawn())

    # Send your moves back to the game environment, ending this turn.
    game.end_turn(command_queue)

