from ollama import AsyncClient
from interactions import SlashCommandOption, Extension, SlashContext, SlashCommandChoice, Task, IntervalTrigger, slash_command
import interactions





class LLM(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot


        
    @slash_command(name='llm',
                   description='Commandes Aram')
    async def llm(self, ctx: SlashContext):  
        pass  



    @llm.subcommand("modele_leger",
                   sub_cmd_description="LLM Leger",
                     options=[
                       SlashCommandOption(
                           name='texte',
                           description="Contenu de la question",
                           type=interactions.OptionType.STRING,
                           required=True)])
    async def llm_leger(self,
                          ctx: SlashContext,
                          texte : str,
                          ):

        await ctx.defer()
        
        message = {'role' : 'user', 
                   'content' : texte}
        
        response = await AsyncClient().chat(model='gpt-oss:20b', messages=[message])

        response_to_send = response['message']['content']
        
        def decouper_texte(texte_cut):
            taille = 1900
            blocs = [texte_cut[i:i+taille] for i in range(0, len(texte_cut), taille)]
            return blocs 
        
        response_list = decouper_texte(response_to_send)
        
        for response_part in response_list:
            await ctx.send(response_part)

    # @llm.subcommand("modele_lourd",
    #                sub_cmd_description="LLM Lourd",
    #                  options=[
    #                    SlashCommandOption(
    #                        name='texte',
    #                        description="Contenu de la question",
    #                        type=interactions.OptionType.STRING,
    #                        required=True)])
    # async def llm_lourd(self,
    #                       ctx: SlashContext,
    #                       texte : str,
    #                       ):

    #     await ctx.defer()
        
    #     message = {'role' : 'user', 
    #                'content' : texte}
        
    #     response = await AsyncClient().chat(model='gpt-oss:120b', messages=[message])

    #     response_to_send = response['message']['content']
        
    #     return await ctx.send(response_to_send)    


def setup(bot):
    LLM(bot)
