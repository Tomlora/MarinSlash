import random


##### Code par kennhh : https://github.com/kennhh/memory-game-discord-bot/tree/main #####

class MemoryGame:
    def __init__(self):
        self.sequence_length = 1
        self.sequence = []
        self.current_index = 0
        self.hidden_game = False

    def generate_sequence(self):
        for i in range(self.sequence_length):
            random_number = random.randint(0,24)
            if self.sequence:
                while random_number == self.sequence[-1]:
                    random_number = random.randint(0, 24)
                self.sequence.append(random_number)
            else:
                self.sequence.append(random_number)

    def sequence_reset(self):
        self.sequence = []
        self.current_index = 0
        self.generate_sequence()

    def successful(self):
        self.sequence_length += 1

    def correct_current_index(self):
        self.current_index += 1