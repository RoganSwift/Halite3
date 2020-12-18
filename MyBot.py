# Python 3.6
# rules: https://web.archive.org/web/20181019011459/http://www.halite.io/learn-programming-challenge/game-overview

""" Stage 0: Imports - Permitted X minutes here
    Access to only code.    
"""

import sys
import json
import logging
import time
import pickle

# Import the Halite SDK, which will let you interact with the game.
import hlt
from hlt import constants, commands # This library contains constant values.
from hlt.positionals import Direction, Position # This library contains direction metadata to better interface with the game.

#sys.argv[0] is "MyBot.py", which we don't need to save.
if len(sys.argv) >= 2:
    logging_level = int(sys.argv[1])
else:
    logging_level = 0

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

def read_moved_ships(command_queue):
    return [int(command.split(' ')[1]) for command in command_queue]

def dir_to_pos(direction):
    return Position(direction[0], direction[1])

reverted_commands = {commands.NORTH: Direction.North,
                     commands.SOUTH: Direction.South,
                     commands.EAST:  Direction.East,
                     commands.WEST:  Direction.West,
                     commands.STAY_STILL: Direction.Still}

def read_committed_positions(ships, command_queue):
    if len(command_queue) > 0:
        result = []
        for command in command_queue:
            _, ship_id, direction = command.split(" ")
            ship = next((x for x in ships if x.id == int(ship_id)), None)
            result.append(ship.position + dir_to_pos(reverted_commands[direction]))
        return result
    else:
        return []

class FlinkBot():
    '''A bot (game state + behaviors) for the Halite competition. Initialization begins hlt.Game().
    FlinkBot.start_game() runs hlt.Game() and starts X minute timer to do pre-processing.
    FlinkBot.ready() begins game.ready().
    '''
    def __init__(self):
        '''Reserve class variables. These must be populated with one of the following:
        * self.start_game() - Used when the bot is intended to run in a loop.
        * self.perform_test() - Used for debugging to sample one game step from a saved game state.
        '''
        self.game = None
        self.game_map = None
        self.me = None
        self.ships = None
        self.q = None
        self.CONSTANTS = None

    def start_game(self):
        ''' Initiate Stage 1: Pre-game scanning - Permitted X minutes here.
        Once game = hlt.Game() is run, you have access to the game map for computationally-intensive start-up pre-processing.
        '''
        self.game = hlt.Game()
        self.game_map = self.game.game_map
        self.me = self.game.me
        self.ships = self.me.get_ships()
        self.CONSTANTS = {
            'SHIP_COST': constants.SHIP_COST,
            'DROPOFF_COST': constants.DROPOFF_COST,
            'MAX_HALITE': constants.MAX_HALITE,
            'MAX_TURNS': constants.MAX_TURNS,
            'EXTRACT_RATIO': constants.EXTRACT_RATIO,
            'MOVE_COST_RATIO': constants.MOVE_COST_RATIO,
            'INSPIRATION_ENABLED': constants.INSPIRATION_ENABLED,
            'INSPIRATION_RADIUS': constants.INSPIRATION_RADIUS,
            'INSPIRATION_SHIP_COUNT': constants.INSPIRATION_SHIP_COUNT,
            'INSPIRED_EXTRACT_RATIO': constants.INSPIRED_EXTRACT_RATIO,
            'INSPIRED_BONUS_MULTIPLIER': constants.INSPIRED_BONUS_MULTIPLIER,
            'INSPIRED_MOVE_COST_RATIO': constants.INSPIRED_MOVE_COST_RATIO,
            'WIDTH': constants.WIDTH,
            'HEIGHT': constants.HEIGHT
        }

        if logging_level >= 1:
            map_array = [
                        [self.game_map[Position(x,y)].halite_amount for x in range(self.game_map.width)] for y in range(self.game_map.height)
                        ]
            sc_log(1, f"##FL-Map:{str(json.dumps(map_array))}")

        p = self.determine_personality_parameters(self.game_map)

        # Apply loaded personality parameters
        self.q = (p[0]*200, # 0 to 200 - Amount of halite in cell where ships consider it depleted.
            (0.5+p[1]*0.25)*self.CONSTANTS['MAX_HALITE'], # 50% to 75% of MAX_HALITE - amount of cargo above which ships believe they're returning cargo.
            1 + round(p[2]*29) # 1 to 30 - max number of bots
        )

    def write_state(self):
        '''Create two files - save_state contains human-readable details about the game state, while pickle_state contains a pickled copy of the game state.'''
        with open("save_states/save_state id%s round%s %s" % (self.game.my_id, self.game.turn_number, int(time.time())),'w') as save_file:
            map_array = [
                        [self.game_map[Position(x,y)].halite_amount for x in range(self.game_map.width)] for y in range(self.game_map.height)
                        ]
            save_file.write("Map: %s\n" % (str(json.dumps(map_array))))
            save_file.write("q: %s\n" % (str(self.q)))
            save_file.write("Halite: %s\n" % (self.game.me.halite_amount))
            ship_data = [(ship.id, ship.position.x, ship.position.y, ship.halite_amount) for ship in self.game.me.get_ships()]
            save_file.write("Ships: %s\n" % (str(json.dumps(ship_data))))
        
        with open("save_states/pickle_state id%s round%s %s" % (self.game.my_id, self.game.turn_number, int(time.time())),'wb') as pickle_file:
            pickle.dump([self.game, self.q, self.CONSTANTS], pickle_file)

    def perform_test(self, pickled_file):
        """Run one turn of the bot starting from the game state in pickled_file.
        
        :param pickled_file: a previously-pickled copy of [self.game, self.q, self.CONSTANTS] from an actual game run.

        :return: command_queue developed over the turn.
        """
        with open(pickled_file, 'rb') as pickled_state:
            state = pickle.load(pickled_state)
        
        self.game = state[0]
        self.game_map = self.game.game_map
        self.me = self.game.me
        self.ships = self.me.get_ships()
        self.q = state[1]
        self.CONSTANTS = state[2]

        # This needs to exist because hlt.constants doesn't accept the same names it provides.
        CONSTANTS_RENAMED_FOR_IMPORT = {
            'map_width': self.CONSTANTS['WIDTH'],
            'map_height': self.CONSTANTS['HEIGHT'],
            'NEW_ENTITY_ENERGY_COST': self.CONSTANTS['SHIP_COST'],
            'DROPOFF_COST': self.CONSTANTS['DROPOFF_COST'],
            'MAX_ENERGY': self.CONSTANTS['MAX_HALITE'],
            'MAX_TURNS': self.CONSTANTS['MAX_TURNS'],
            'EXTRACT_RATIO': self.CONSTANTS['EXTRACT_RATIO'],
            'MOVE_COST_RATIO': self.CONSTANTS['MOVE_COST_RATIO'],
            'INSPIRATION_ENABLED': self.CONSTANTS['INSPIRATION_ENABLED'],
            'INSPIRATION_RADIUS': self.CONSTANTS['INSPIRATION_RADIUS'],
            'INSPIRATION_SHIP_COUNT': self.CONSTANTS['INSPIRATION_SHIP_COUNT'],
            'INSPIRED_EXTRACT_RATIO': self.CONSTANTS['INSPIRED_EXTRACT_RATIO'],
            'INSPIRED_BONUS_MULTIPLIER': self.CONSTANTS['INSPIRED_BONUS_MULTIPLIER'],
            'INSPIRED_MOVE_COST_RATIO': self.CONSTANTS['INSPIRED_MOVE_COST_RATIO']
        }
        hlt.constants.load_constants(CONSTANTS_RENAMED_FOR_IMPORT)
        
        return self.one_game_step()

    def determine_personality_parameters(self, game_map):
        '''Determine a number between 0 and 1 for each of the personality parameters.
        
        Presently, this is grabbed from system arguments when the bot is called, but the intention is for a trained machine-learning bot to read the map and choose optimal parameters.'''
        # TODO: game_map is not currently used. The intention is to train a machine learning algorithm to determine these parameters from the game map.

        #sys.argv[0] is "MyBot.py", which we don't need to save.
        #sys.argv[1] is the logging level, which is captured elsewhere.

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
        
        return p

    def ready(self):
        ''' Initiate Stage 2: Game Turns - Permitted 2 seconds per turn.
        Once game.ready("MyPythonBot") is run, you have access to positions of units and the ability to send commands.
        '''
        self.game.ready("MyPythonBot")

        sc_log(1, "Successfully created bot! My Player ID is {}.".format(self.game.my_id))

    def update(self):
        '''Pull updated game state data from the game and update class variables.'''
        self.game.update_frame() # pull updated data
        self.me = self.game.me
        self.ships = self.me.get_ships()

    def submit(self, command_queue):
        '''Submit the completed command queue.

        self.game.end_turn(command_queue)
        '''
        self.game.end_turn(command_queue)

    def one_game_step(self):
        '''Determine and return the command_queue actions to take this turn.'''
        sc_log(1, f"##FL-Round:{self.game.turn_number}:{self.game.me.halite_amount}")

        command_queue = []

        #TODO: Consider enemy positions when choosing to move
        #      If you can't grab a list of their positions, spiral_walk until you find the closest.
        for ship in self.ships:
            if ship.id not in read_moved_ships(command_queue):
                command_queue = self.move_ship_recursive(command_queue, ship, [])

        if self.me.halite_amount >= self.CONSTANTS['SHIP_COST'] and self.me.shipyard.position not in read_committed_positions(self.ships, command_queue) and len(self.ships) <= self.q[2]:
            sc_log(2, "Generating new ship.")
            command_queue.append(self.me.shipyard.spawn())

        sc_log(1, f"Command queue: {str(command_queue)}")
        return command_queue

    def move_ship_recursive(self, command_queue, ship, ignore_ships):
        '''Determine ship movement, recursively deferring to a ship in its path and ignoring ships that are confirmed to move elsewhere.'''
        sc_log(1, f"Move_ship_recursion start: Ship {ship.id}")

        moved = False
        loopcounter = 0 # Infinite loops terrify me, so loopcounter has a max of 10, which should never occur. (Actual max 5)
        while not moved and loopcounter < 10:
            # Check for the ship's desired move, considering that it can't go to any committed positions
            move_direction, move_position = self.desired_move(ship, command_queue)
            sc_log(1, "Move_ship_recursion: Ship {ship.id} considering direction {move_direction} position {move_position}")
            # Collisions are only possible with ships meeting the following criteria:
            # (1) has not moved yet and (2) is currently on the target space
            #  - Ships after this ship won't target this target because it will be in the command queue once this ship commits
            #  - and this ship couldn't have targeted this space if another ship committed to staying still in it.
            # (3) is not higher in the recursive chain than this ship
            #  - you know any ship higher up the chain wants to move from its spot
            # To resolve this, check every ship for these three criteria
            no_ships_on_target = True
            for other_ship in self.ships:
                if ship.id != other_ship.id and other_ship.position == move_position and other_ship.id not in ignore_ships and other_ship.id not in read_moved_ships(command_queue):
                    sc_log(1, f"Move_ship_recursion: Ship {ship.id} blocked by {other_ship}. Letting it go first.")
                    # If one is found, let it move first, ignoring this ship (criteria (3) above)
                    ignore_ships_copy = [iship for iship in ignore_ships]
                    ignore_ships_copy.append(ship.id)
                    command_queue = self.move_ship_recursive(command_queue, other_ship, ignore_ships_copy)
                    # If that ship (or its down-chain friends) decided to commit this spot,
                    #   we need to restart the while loop and desired_move elsewhere.
                    if move_position in read_committed_positions(self.ships, command_queue):
                        no_ships_on_target = False
                        break

            # If, after looking at all other ships, none meet the criteria and want to stay, we can commit the move.
            if no_ships_on_target:
                if move_direction == "stay":
                    sc_log(1, f"Move_ship_recursion: Ship {ship.id} decided to stay at {ship.position}")
                    command_queue.append(ship.stay_still())
                else:
                    sc_log(1, f"Move_ship_recursion: Ship {ship.id} decided to move {move_direction} to {move_position}")
                    command_queue.append(ship.move(move_direction)) 
                moved = True
            
            loopcounter += 1
        
        # As above, if the while loop goes way beyond where it should, fail gracefully and log.
        if not moved:
            sc_log(1, f"FLWarning:Ship {ship.id} could not find a target in 10 checks")
            command_queue.append(ship.stay_still())

        return command_queue

    def desired_move(self, ship, command_queue):
        '''Determine the move which gets the given ship closest to its desired target, forbidding claimed spaces in the command_queue.'''
        committed_positions = read_committed_positions(self.ships, command_queue)
        on_shipyard = (self.me.shipyard.position == ship.position)
        sc_log(3, f"Invalid Positions: {str(committed_positions)}")
        sc_log(2, "- Checking desired move for ship {}.".format(ship.id))
        position = ship.position
        target = self.determine_target(ship)

        if ship.halite_amount < self.game_map[ship.position].halite_amount*0.1 or position == target:
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
            offset_pos = position +Position(option[0], option[1])
            diagonal_distance = dist_betw_positions(offset_pos, target)
            if diagonal_distance < best_distance and offset_pos not in committed_positions:
                move_order = option
                destination = offset_pos
                best_distance = diagonal_distance

        sc_log(2, f"- - Next step for ship {ship.id} is {str(move_order)} to {str(destination)}")        
        return (move_order, destination)

    def determine_target(self, ship):
        '''Determine where the ship wants to end up, based on its current status and the map.'''
        # If ship is full or (ship is on a drained square and carrying lots of halite)
        if ship.halite_amount == self.CONSTANTS['MAX_HALITE'] or (ship.halite_amount > self.q[1] and self.game_map[ship.position].halite_amount < self.q[0]):
            sc_log(3, f"- - Target for ship {ship.id} is shipyard.")
            return self.me.shipyard.position
        else:
            cells_searched = 0
            for search_position in spiral_walk(ship.position.x, ship.position.y):
                sc_log(3, f"- - - Checking search position {str(search_position)} with {self.game_map[search_position].halite_amount} halite.")
                if self.game_map[search_position].halite_amount >= self.q[0]:
                    sc_log(3, f"- - - Target for ship {ship.id} is {str(search_position)}")
                    return search_position

                # If there is insufficient halite on the map (very high threshold for depleted), stop.
                cells_searched += 1
                if cells_searched > 4*max(self.CONSTANTS['WIDTH'], self.CONSTANTS['HEIGHT'])**2: # this is worst-case of sitting in a corner
                    sc_log(1, f"??? Search found insufficient halite on map - ordering ship not to move.")
                    return ship.position    

if __name__ == "__main__":
    flink_bot = FlinkBot()
    flink_bot.start_game() # Initializes, runs hlt.Game() and starts X minute timer to do pre-processing
    flink_bot.ready() # Readying starts 2-second turn timer phase

    while True:
        try:
            # Grab updated game map details
            flink_bot.update()
            # Determine set of commands
            command_queue = flink_bot.one_game_step()
            # Submit commands
            flink_bot.submit(command_queue)
        except Exception:
            flink_bot.write_state()
            raise
