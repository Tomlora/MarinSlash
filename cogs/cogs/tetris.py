

import interactions
from interactions import slash_command, listen, Client, SlashContext, ActionRow, Button, ButtonStyle, Task, IntervalTrigger, PartialEmoji, Extension
from fonctions.tetris_game_logic import TetrisGame, GameOver
from interactions.api.events import Component


###### Code par kennhh : https://github.com/kennhh/tetris-discord-bot ######


class Tetris(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

        self.game = TetrisGame()


    @Task.create(IntervalTrigger(seconds=1))
    async def game_task(self, ctx, message):
        try:
            self.game.tick()
            embed_color = 0xFFFFFF if self.game.cleared_line else None
            game_field = interactions.EmbedField(
                name=f'score: {self.game.score}',
                value=self.game.draw(),
                inline= True
            )
            hold_field = interactions.EmbedField(
                name='holding',
                value=self.game.get_held_block_visual(),
                inline=True
            )
            embed = interactions.Embed(fields=[game_field, hold_field], color=embed_color)
            await message.edit(embed=embed.to_dict())
        except GameOver:
            self.game_task.stop()
            game_field = interactions.EmbedField(
                name=f'game over | score: {self.game.score}',
                value=self.game.draw(),
                inline= True
            )
            hold_field = interactions.EmbedField(
                name='holding',
                value=self.game.get_held_block_visual(),
                inline=True
            )
            embed = interactions.Embed(fields=[game_field, hold_field])
            await message.edit(embed=embed.to_dict(), components=[])
            self.game.__init__()


    @slash_command(name='tetris', description='Joue au Tetris')
    async def start(self, ctx: SlashContext):
        tetrisbuttons = [
            ActionRow(
                Button(
                    style=ButtonStyle.BLURPLE,
                    emoji=PartialEmoji.from_str(':left_right_arrow:'),
                    custom_id='hold'
                ),
                Button(
                    style=ButtonStyle.BLURPLE,
                    emoji=PartialEmoji.from_str(':arrows_counterclockwise:'),
                    custom_id='rotate'
                ),
                Button(
                    style=ButtonStyle.DANGER,
                    emoji=PartialEmoji.from_str(':stop_button:'),
                    custom_id='stop_tetris'
                )
            ),
            ActionRow(
                Button(
                    style=ButtonStyle.BLURPLE,
                    emoji=PartialEmoji.from_str(':arrow_left:'),
                    custom_id="left",
                ),
                Button(
                    style=ButtonStyle.BLURPLE,
                    emoji=PartialEmoji.from_str(':arrow_down:'),
                    custom_id='hard_drop'
                ),
                Button(
                    style=ButtonStyle.BLURPLE,
                    emoji=PartialEmoji.from_str(':arrow_right:'),
                    custom_id='right'
                )
            )
        ]
        empty_hold_field = '\n'.join([':black_large_square:' * 4 for _ in range(4)])
        game_field = interactions.EmbedField(
            name='score: 0',
            value=self.game.draw(),
            inline=True
        )
        hold_field = interactions.EmbedField(
            name='holding',
            value= empty_hold_field,
            inline=True
        )
        embed = interactions.Embed(fields=[game_field, hold_field])
        embed_msg = await ctx.send(embed=embed.to_dict(), components=tetrisbuttons)
        self.game_task.start(ctx, embed_msg)


    @listen()
    async def on_component(self, event: Component):
        ctx = event.ctx
        match ctx.custom_id:
            case 'left':
                self.game.move("left")
                await ctx.send("", ephemeral=True)
            case 'right':
                self.game.move("right")
                await ctx.send("", ephemeral=True)
            case 'rotate':
                self.game.rotate()
                await ctx.send("", ephemeral=True)
            case 'hard_drop':
                self.game.hard_drop()
                await ctx.send("", ephemeral=True)
            case 'hold':
                self.game.swap_with_hold()
                await ctx.send("", ephemeral=True)
            case 'stop_tetris':
                self.game_task.stop()
                await ctx.send("", ephemeral=True)
                
                
def setup(bot):
    Tetris(bot)