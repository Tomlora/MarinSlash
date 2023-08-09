
import interactions
from interactions import Client, Task, SlashContext, listen, slash_command, IntervalTrigger, Button, ButtonStyle, SlashCommandOption, OptionType, Extension

from fonctions.memory_game_logic import MemoryGame
from interactions.api.events import Component

##### Code par kennhh : https://github.com/kennhh/memory-game-discord-bot/tree/main #####


class Memory(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

        self.game = MemoryGame()


    @Task.create(IntervalTrigger(seconds=1.5))
    async def memory_game_task(self, message, current_index):
        buttons = []
        if current_index < self.game.sequence_length:
            for i in range(25):
                if i == self.game.sequence[current_index]:
                    buttons.append(
                        Button(style = ButtonStyle.BLUE, label = f'{i}' if self.game.hidden_game == False else '‍', custom_id = f'{i}', disabled=True)
                    )
                else:
                    buttons.append(
                        Button(style = ButtonStyle.GRAY, label = f'{i}' if self.game.hidden_game == False else '‍', custom_id = f'{i}', disabled=True)
                    )
            actionrowbuttons = interactions.spread_to_rows(*buttons)
            await message.edit(components = actionrowbuttons)
            self.memory_game_task.restart(message, current_index + 1)
        else:
            for i in range(25):
                buttons.append(
                    Button(style = ButtonStyle.GRAY, label = f'{i}' if self.game.hidden_game == False else '‍', custom_id = f'{i}', disabled=False)
                )
            actionrowbuttons = interactions.spread_to_rows(*buttons)
            await message.edit(components = actionrowbuttons)
            self.memory_game_task.stop()


    @slash_command(
            name='memory_game',
            description='Joue au memory game',
            options=[
                SlashCommandOption(
                    name='hidden_game',
                    description='Cache les nombres (off par default)',
                    type=OptionType.BOOLEAN,
                    required=False
                )
            ])
    async def memory(self, ctx: SlashContext, hidden_game: bool = False):
        await ctx.defer()
        self.game.hidden_game = hidden_game
        self.game.generate_sequence()
        buttons = []
        for i in range(25):
            buttons.append(
                Button(style = ButtonStyle.GRAY, label = f'{i}' if self.game.hidden_game == False else '‍', custom_id = f'{i}', disabled=True)
            )
        actionrowbuttons = interactions.spread_to_rows(*buttons)
        message = await ctx.send(components=actionrowbuttons)
        self.memory_game_task.start(message, 0)




    @listen()
    async def on_component(self, event: Component):
        ctx = event.ctx
        sequence = self.game.sequence
        current_index = self.game.current_index
        custom_id = ctx.custom_id
        match ctx.custom_id:
            case str(custom_id):
                if int(custom_id) == int(sequence[current_index]):
                    if len(sequence) == current_index + 1:
                        self.game.successful()
                        self.game.sequence_reset()
                        self.memory_game_task.start(ctx.message, 0)
                    else:
                        self.game.correct_current_index()
                    await ctx.send("", ephemeral=True)
                else:
                    self.game.__init__()
                    buttons = []
                    for i in range(25):
                        if i == sequence[current_index]:
                            buttons.append(
                                Button(style = ButtonStyle.GREEN, label = f'{i}', custom_id = f'{i}', disabled=True)
                            )
                        elif i == int(custom_id):
                            buttons.append(
                                Button(style = ButtonStyle.RED, label = f'{i}', custom_id = f'{i}', disabled=True)
                            )
                        else:
                            buttons.append(
                                Button(style = ButtonStyle.GRAY, label = f'{i}', custom_id = f'{i}', disabled=True)
                            )
                    actionrowbuttons = interactions.spread_to_rows(*buttons)
                    embed = interactions.Embed(description=f'uh oh, Tu as validé {custom_id} au lieu de {sequence[current_index]}\n'
                                                        f'La suite correcte était {sequence} ce qui correspond à {len(sequence)} 3 nombres')
                    await ctx.edit_origin(embed=embed.to_dict(), components=actionrowbuttons)
                    

def setup(bot):
    Memory(bot)