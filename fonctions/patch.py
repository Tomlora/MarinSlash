import requests
from bs4 import BeautifulSoup
from markdownify import markdownify

import pandas as pd


                
class PatchNote:
    
    headers = {'Accept': 'application/json'}

    base_url = "https://www.leagueoflegends.com/page-data/"
    patchs_notes_menu_url = '/news/tags/patch-notes/'
    end_url = "page-data.json"
    view_url = "https://www.leagueoflegends.com/"

    langs = [
        'en-gb',
        'fr-fr',
        'de-de',
        'es-es',
        'en-us',
        'it-it',
        'en-pl',
        'pl-pl',
        'el-gr',
        'ro-ro',
        'hu-hu',
        'cs-cz',
        'es-mx',
        'pt-br',
        'ja-jp',
        'ru-ru',
        'tr-tr',
        'en-au',
        'ko-kr'
        ]
    
    def __init__(self, previous : int = 0, lang : str = 'fr-fr'):
        
        if lang not in self.langs:
            print(f"Specified langage is not available. The list of available lang is:\n{self.langs}")
            raise ValueError
   
        
        self.menu_request_url : str = self.base_url+lang+self.patchs_notes_menu_url+self.end_url
        
        try:
            patch_notes_menu_data = requests.get(self.menu_request_url, headers=self.headers).json()
        except Exception:
            print(f"An error occured during the requests of the patchnotes menu data at url '{self.menu_request_url}'. Maybe 'lang' is not correct.")
            raise
        
        try:
            patch_note_url = patch_notes_menu_data['result']['data']['articles']['nodes'][previous]['url']['url']
        except Exception:
            print(f"An error occured while extracting the patch note url from the patchnotes menu.")
            raise
        
        self.link :str = self.view_url + lang + patch_note_url 
        self.patch_request_url : str = self.base_url+lang+patch_note_url+self.end_url
        
        try:
            self.data = requests.get(self.patch_request_url, headers=self.headers).json()
        except Exception:
            print(f"An error occured during the request of the patchnote data at url '{self.patch_request_url}'")
            raise
        
        try:
            self.title : str = self.data['result']['data']['all']['nodes'][0]['description']
        except Exception:
            self.title : str = "Patch title"
            print(f"Unable to found patch note title from the patchnote data. Placeholder text used instead.")
    
        
        try:
            [self.season_number, self.patch_number] = self.data['result']['data']['all']['nodes'][0]['url']['url'].split('/')[3].split('-')[1:3]
        except Exception:
            [self.season_number, self.patch_number] = [0,0]
            print(f"Unable to found season_number and patch_number from the patchnote data. Placeholder values used instead.")
            
      
        self.soup = BeautifulSoup(self.data['result']['data']['all']['nodes'][0]['patch_notes_body'][0]['patch_notes']['html'], 'html.parser')
        

        try:
            self.description : str = markdownify(str(self.soup.blockquote),  heading_style="ATX").replace('>','').strip().replace("\n \n", "\n")
        except Exception:
            self.description : str = "Description of the patch note."
            print(f"Unable to found patch description from patchnote data. Placeholder text used instead.")
        
        try:
            self.overview_image : str = self.soup.find(attrs={"class": "skins cboxElement"}).img.get('src')
        except Exception:
            self.overview_image : str = "https://images.contentstack.io/v3/assets/blt731acb42bb3d1659/blt8536634d0d5ace2a/5e4f14a406f84d0d618d93ea/LOL_PROMOART_12.jpg"
            print(f"Unable to found patch overview image from patchnote data. Placeholder image used instead.")
            
        self.version_patch = str(f"{self.season_number}.{self.patch_number}")
        
        try:
            self.test : str = markdownify(str(self.soup.find('title')),  heading_style="ATX").replace('>','').strip().replace("\n \n", "\n")
        except Exception:
            self.test : str = "Description of the patch note."
            print(f"Unable to found patch description from patchnote data. Placeholder text used instead.")
            
            
    def patch_detail(self):
        self.detail_patch = self.soup.find_all(class_=["change-title", "summary", "change-detail-title ability-title", "attribute-change"])
        self.detail_patch = markdownify(str(self.detail_patch),  heading_style="ATX").replace('>','').strip().replace("\n \n", "\n").replace(",", "").replace("####", "").replace("###", "")
        

            
  