# Python 3.6
# rules: https://web.archive.org/web/20181019011459/http://www.halite.io/learn-programming-challenge/game-overview

# Import the Halite SDK, which will let you interact with the game.
import hlt

if __name__ == "__main__":
    game = hlt.Game()
    game.ready("EmptyBot") # Readying starts 2-second turn timer phase

    while True:
        game.update_frame()
        command_queue = ""
        game.end_turn(command_queue)

