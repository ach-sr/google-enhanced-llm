from urllib.request import urlopen
from bs4 import BeautifulSoup
from urllib.request import urlopen
import requests, json, sys, re, time

data_file_keep = 'data.json'
url_file = 'urls.json'
convo_context = ''

AMOUNT_LINKS, API_KEY, SEARCH_ENGINE_ID, EXCLUDED_SITES, OLLAMA_MODEL, OLLAMA_API_URL, SEARCH_URL, check_exclude, config_to_use = None, None, None, None, None, None, None, None, None


def set_config(new_config):
    amount_excluded = ''
    global API_KEY, SEARCH_ENGINE_ID, EXCLUDED_SITES, OLLAMA_MODEL, OLLAMA_API_URL, AMOUNT_LINKS, SEARCH_URL, check_exclude
    try:
        with open('config.json', 'r+') as config_file:
            print('Retrieving config...')
            config_data = json.load(config_file)
            configs = config_data['config']

            new_config = str(int(new_config)-1)

            configs = config_data['config'][int(new_config)]

            API_KEY = configs['API_KEY']
            SEARCH_ENGINE_ID = configs['SEARCH_ENGINE_ID']
            EXCLUDED_SITES = configs['EXCLUDED_SITES']
            OLLAMA_MODEL = configs['OLLAMA_MODEL']
            OLLAMA_API_URL = configs['OLLAMA_API_URL']
            AMOUNT_LINKS = configs['AMOUNT_LINKS']
            AMOUNT_LINKS = int(AMOUNT_LINKS)
            SEARCH_URL = configs['SEARCH_URL']

            if EXCLUDED_SITES != '' or EXCLUDED_SITES != 'none':
                check_exclude = True
            else: check_exclude = False

            amount_excluded = EXCLUDED_SITES.split(', ')

            #Set config chosen:
            config_file.seek(0)
            config_data['config_chosen'] = str(new_config)
            json.dump(config_data, config_file, indent=4)

        print(f'Config {int(config_to_use)} pulled successfully:\n  Model: {OLLAMA_MODEL}\n  Amount links (to search for): {AMOUNT_LINKS}\n  Excluding the following sites({len(amount_excluded)}): {EXCLUDED_SITES}')
    except Exception as e:
        print(f"An unexpected error occured: {e}")
        sys.exit()

def get_amount_config():
    try:
        with open('config.json', 'r') as config_file:
            config_data = json.load(config_file)
            configs = config_data['config']
        return len(configs)
    except Exception as e:
        print(f"An unexpected Error occured: {e}")
        sys.exit()

def search_engine_request(to_send, api_key, se_id, url):
    params = {
        'q': to_send,
        'key': api_key,
        'cx': se_id
    }
    response = requests.get(url, params=params)
    results = response.json()
    return results

def load_links(filename='urls.json'):
    try:
        with open(filename, 'r') as links_file:
            links_data = json.load(links_file)
    except Exception as e:
        print(f'An unexpected error occured: {e}\nIs the urls.json file empty?')
        sys.exit()
    links = links_data['links']
    return links

def scrape(all_links, tag, max_chars_per_link=3400): # returns 2 things: 1. scraped_data list, should be saved in json       2. data_to_give, string to give to model as data
    data_to_give = ''
    scraped_data = []
    for link_info in all_links:
        link_id = link_info['id']
        link_url = link_info['link']

        try:
            response = requests.get(link_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            paragraphs = soup.find_all(tag)
            extracted_text = ' '.join(paragraph.text for paragraph in paragraphs)
            extracted_text = extracted_text.replace('\n', '').replace('\t', '').replace('\u2013', '').replace('\u2019', '').replace('\u201d', '').replace('\u00a0', '').replace('\u201c', '')

            data_to_give += extracted_text[:max_chars_per_link]
            stored_given = extracted_text[:max_chars_per_link]

            scraped_data.append({
                'id': link_id,
                'link': link_url,
                'scraped_text': extracted_text,
                'text_given_to_model': stored_given
            })
            # all_data += extracted_text

            print(f"Scraped successfully from link {link_id+1}: {link_url}")

        except requests.RequestException as e:
            print(f"WARNING: unable to scrape data from link {link_id+1} ({link_url}): {e}")
            # no need to sys.exit() here, only a warning.
    
    return scraped_data, data_to_give

def ollama_call(input_query, data_for_model, model, ollama_api_url, context=None):
    if context is None:
        prompt = f"Respond directly to the following prompt: {input_query}\nIf needed, use the following data to help respond:{data_for_model}\nIgnore all data irrelevant to the question.\nIf you used the data, say where in the data you got your answer from. Do not make up answers."

        data = {
            "model": model,
            "prompt": prompt
        }
    elif context is not None:
        prompt = f"Answer this follow up question: {input_query}\nIf you need to, use this data: {data_for_model}\nIf you used the data, say where in the data you got your answer from. Do not make up answers."
        data = {
            "model": model,
            "prompt": prompt,
            "context": context
        }

    try:
        print('Waiting for response...')
        response = requests.post(ollama_api_url, json=data)
    except Exception as e:
        print(f"An unexpected error occured: {e}. Did you forget 'ollama serve'?")
        sys.exit()
    except requests.exceptions.RequestException as e:
        print(f"An unexpected error occurred: {e}. Did you forget 'ollama serve'?")
        sys.exit()
    return response


print("Welcome to google enhanced llm search!\n")

config_to_use = input(f"Which config to use? (int, currently {get_amount_config()} configs): ")
set_config(config_to_use)
print('')

# chatting sequence
while(True):
    links_list = []
    all_response = ''

    query = input(">> ")
    search_query = query

    with open('config.json', 'r+') as config_file:
        config_data = json.load(config_file)
        config_file.seek(0)
        config_data['prompt'] = str(query)
        json.dump(config_data, config_file, indent=4)
        config_file.truncate()

    if check_exclude == True:
        excluded_sites = EXCLUDED_SITES.split(', ')
        for i, site in enumerate(excluded_sites):
            search_query += f' -site:{site}'
    else: print('Not excluding sites, continuing...')

    print(f"Final search engine query: {search_query}\n")

    # Acquiring links
    results = search_engine_request(search_query, API_KEY, SEARCH_ENGINE_ID, SEARCH_URL)

    if 'items' in results:
        for i in range(min(AMOUNT_LINKS, len(results['items']))):
            link = results['items'][i]['link']
            links_list.append(link)

    print("Links:")
    for i, link in enumerate(links_list, start=1):
        print({link})
    print(f'{i} link(s)')

    print('Saving...')
    data = {"links": []}

    for idx, link in enumerate(links_list):
        save_info = {
            "id": idx,
            "link": link
        }
        data["links"].append(save_info)

    with open('urls.json', 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, indent=4)
    print('Done')


    # Scraping process
    links = load_links()
    scraped_results = scrape(links, 'p')
    scraped_data, data_to_give = scraped_results

    print('Saving scraped data')
    with open(data_file_keep, 'w') as data_file:
        json.dump(scraped_data, data_file, indent=4)

    print('')
    # llm process:
    if convo_context == '':
        response = ollama_call(query, data_to_give, OLLAMA_MODEL, OLLAMA_API_URL, context=None)
    else:
        # print('Context found, reply')
        response = ollama_call(query, data_to_give, OLLAMA_MODEL, OLLAMA_API_URL, context=convo_context)

    print('\nResponse:')
    for line in response.iter_lines(decode_unicode=True):
        if line:
            try:
                json_data = json.loads(line)
                if json_data['done'] == False:
                    final_response = json_data['response']
                    print(final_response, end='')

                    all_response += json_data['response']
                else: convo_context = json_data['context']
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
    

    # print(f'\n{all_response}')
    print('\n')