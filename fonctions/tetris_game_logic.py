from enum import Enum
import random


###### Code par kennhh : https://github.com/kennhh/tetris-discord-bot ######

class Block(Enum):
    EMPTY = '⬛'
    I = '🟦'
    O = '🟨'
    T = '🟪'
    S = '🟩'
    Z = '🟥'
    J = '🟫'
    L = '🟧'

class Shape(Enum):
    I = [(0, 0), (-1, 0), (1, 0), (2, 0)] 
    O = [(0, 0), (0, 1), (1, 0), (1, 1)]  
    T = [(0, 0), (-1, 0), (1, 0), (0, 1)] 
    S = [(0, 0), (1, 0), (0, 1), (-1, 1)] 
    Z = [(0, 0), (-1, 0), (0, 1), (1, 1)] 
    J = [(0, 0), (-1, 0), (1, 0), (1, 1)] 
    L = [(0, 0), (-1, 0), (1, 0), (-1, 1)]

class TetrisGame:
    WIDTH = 10
    HEIGHT = 19 #why 19? because 20 cuts off for some reason. havent looked into it

    def __init__(self):
        self.grid = [[Block.EMPTY for _ in range(self.WIDTH)] for _ in range(self.HEIGHT)]
        self.current_pos = (0, self.WIDTH // 2)
        self.current_shape = None
        self.current_block = None
        self.spawn_new_shape()
        self.cleared_line = False
        self.held_block = None
        self.held_shape = None
        self.has_swapped_this_turn = False
        self.score = 0

    def spawn_new_shape(self):
        shape_type = random.choice(list(Shape))
        self.current_shape = shape_type.value
        self.current_block = Block[shape_type.name]
        min_x = min(dx for dx, dy in self.current_shape)
        max_y = max(dy for dx, dy in self.current_shape)
        self.current_pos = (abs(min_x), self.WIDTH // 2 - max_y)
        self.has_swapped_this_turn = False
        x, y = self.current_pos
        if any(self.grid[x + dx][y + dy] != Block.EMPTY for dx, dy in self.current_shape):
            raise GameOver(Exception)

    def tick(self):
        x, y = self.current_pos
        if any(x + dx + 1 == self.HEIGHT or self.grid[x + dx + 1][y + dy] != Block.EMPTY for dx, dy in self.current_shape):
            for dx, dy in self.current_shape:
                self.grid[x + dx][y + dy] = self.current_block
            self.spawn_new_shape()
            self.has_swapped_this_turn = False
        else:
            self.current_pos = (x + 1, y)
        self.clear_rows()

    def clear_rows(self):
        i = 0
        self.cleared_line = False
        while i < len(self.grid):
            if all(cell != Block.EMPTY for cell in self.grid[i]):
                del self.grid[i]
                self.grid.insert(0, [Block.EMPTY for _ in range(self.WIDTH)])
                self.score += 1
                self.cleared_line = True
            else:
                i += 1

    def move(self, direction):
        x, y = self.current_pos
        if direction == "left" and all(0 <= y + dy - 1 and self.grid[x + dx][y + dy - 1] == Block.EMPTY for dx, dy in self.current_shape):
            self.current_pos = (x, y - 1)
        elif direction == "right" and all(y + dy + 1 < self.WIDTH and self.grid[x + dx][y + dy + 1] == Block.EMPTY for dx, dy in self.current_shape):
            self.current_pos = (x, y + 1)

    def rotate(self):
        new_shape = [(dy, -dx) for dx, dy in self.current_shape]
        x, y = self.current_pos
        if all(0 <= x + dx < self.HEIGHT and 0 <= y + dy < self.WIDTH and self.grid[x + dx][y + dy] == Block.EMPTY for dx, dy in new_shape):
            self.current_shape = new_shape 
        else: #wall kicking
            for i in range(-2, 3): 
                if all(0 <= x + dx < self.HEIGHT and 0 <= y + dy + i < self.WIDTH and self.grid[x + dx][y + dy + i] == Block.EMPTY for dx, dy in new_shape):
                    self.current_shape = new_shape
                    self.current_pos = (x, y + i)
                    break

    def draw(self):
        x, y = self.current_pos
        grid = [row.copy() for row in self.grid]
        for dx, dy in self.current_shape:
            grid[x + dx][y + dy] = self.current_block
        return '\n'.join(''.join(cell.value for cell in row) for row in grid)
    
    def hard_drop(self):
        x, y = self.current_pos
        while not any(x + dx + 1 == self.HEIGHT or self.grid[x + dx + 1][y + dy] != Block.EMPTY for dx, dy in self.current_shape):
            x += 1
        self.current_pos = (x, y)
        for dx, dy in self.current_shape:
            self.grid[x + dx][y + dy] = self.current_block
        self.spawn_new_shape()

    def swap_with_hold(self):
        if self.has_swapped_this_turn:
            return
        if self.held_shape is None:
            self.held_shape = self.current_shape
            self.held_block = self.current_block
            self.spawn_new_shape()
        else:
            self.current_shape, self.held_shape = self.held_shape, self.current_shape
            self.current_block, self.held_block = self.held_block, self.current_block
            min_x = min(dx for dx, dy in self.current_shape)
            max_y = max(dy for dx, dy in self.current_shape)
            self.current_pos = (abs(min_x), self.WIDTH // 2 - max_y)
        self.has_swapped_this_turn = True

    def get_held_block_visual(self):
        grid = [[Block.EMPTY for _ in range(4)] for _ in range(4)]
        if self.held_shape is not None:
            for dx, dy in self.held_shape:
                grid[dx + 1][dy + 1] = self.held_block
        return '\n'.join(''.join(cell.value for cell in row) for row in grid)

class GameOver(Exception):
    pass