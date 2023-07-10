import requests
import sys
from slack_utils import SlackUtils

#accept args
repo_name = sys.argv[1]
pr_name = sys.argv[2]

#strip 'alkiranet/' from repo name
repo_name = repo_name[10:]

print(f"Repository name: {repo_name}")
print(f"Pull request name: {pr_name}")

#jira endpoints and tokens
jira_api_token = ('ATATT3xFfGF0jziySlqbHSevK_aDiyOnEr8HvDebGvMekqe'
                  +'c4jPd0soDu5gCpa1kJwB-iJ4kdbuYNCscKr7GC3f54PWdi'
                  +'CfLRSP6w1MjD1yzW65DB1m_hZ-L0NAdk4_D5mPBVhc7ir4'
                  +'HbBPuMdd7k0eGiWIkUk_JDagbPhRLe38AJNa_GcUsEZk=A67922D2')


issue_endpoint = 'https://alkiranet.atlassian.net/rest/api/2/issue/'

#initialize slack utils object
slack_utils = SlackUtils()

issuetype = None

notion_key = 'secret_JSScHYv7GGUgX1ddBp85lK2ecq8POM4oHhn2JBDHYbY'
table_id = '38a9c874720d4e4bb202d07159733f31'
url = f"https://api.notion.com/v1/databases/{table_id}/query"

payload = {"page_size": 100}
headers = {
    "Authorization": "Bearer "+notion_key,
    "accept": "application/json",
    "Notion-Version": "2022-06-28",
    "content-type": "application/json"
}

#create and log message to slack
def post_to_slack(status):
    #slack_utils.__load_slack("/Users/arnav/Documents/Code/token.yaml")

    # Define message text
    if issuetype is not None:
        message_text = f"Repo: {repo_name} \t AK: {pr_name} \t Type: {issuetype} \t {status}"
    else:
        message_text = f"Repo: {repo_name} \t AK: {pr_name} \t {status}"

    # Use the create_slack_message method to post the message to the channel
    try:
        slack_utils.create_slack_message("git-notion-log", message_text)
    except:
        print('Issue with Slack log, could not create message.')
    
#post the repo name to repo column of Notion table
#corresponding with AK number
def post_to_table(ak_num, name):

    #find AK number in Notion
    search_filter = {
        "property": "AK-Story",
            "rich_text": {
                "contains": ak_num
            }
    }
   
    #get page ID (row) that corresponds to AK num
    response = requests.post(url, headers=headers, json={"filter":search_filter})
    if not response.json()['results']:
        print(f'{ak_num} not found in Notion.')
        post_to_slack(f'{ak_num} not found in Notion.')
        print(type(ak_num))
        return     #safely exit method if AK story not found in Notion
        
    results = response.json()['results'][0]
    page_id = results['id']
    #get page id and current repos to append new repo name
    current_repos = results["properties"]["Repositories"]["multi_select"]
    
    #patch to the database the repo name
    current_repos.append({"name": name})
    post_repo = {
        "Repositories": {
            "multi_select": current_repos
        }
    }

    #post to the Repo column the repo name
    post_url = f"https://api.notion.com/v1/pages/{page_id}"
    response = requests.patch(post_url, headers=headers, json={"properties":post_repo})

    post_to_slack(f'{ak_num} found and updated in Notion.')
    
    print()
    print(response.json())


#main script
try:
    response = requests.get(issue_endpoint + pr_name, auth=('arnav.raut@alkira.net',
                                    jira_api_token))
    issuetype = response.json()['fields']['issuetype']['name']

except:
	print("Exception, issue with Jira GET call.")
	post_to_slack("Exception, issue with Jira GET call.")
	sys.exit(0)

if issuetype == 'Sub-task': #find if issue is sub-task
    parent = response.json()['fields']['parent']['key']
    print('This is a sub-task')
    print(f'Parent is {parent}')
    try:
        post_to_table(parent, repo_name)
    except:
        print("Exception, issue with Notion GET call.")
        post_to_slack("Exception, issue with Notion.")
    

elif issuetype == 'Story' :
    print('This is a Story')
    try:
        post_to_table(pr_name, repo_name)
    except:
        print("Exception, issue with Notion GET call.")
        post_to_slack("Exception, issue with Notion.")

elif issuetype == 'Bug':
    print('This is a Bug')
    for issue in response.json()['fields']['issuelinks']:
        try:  #try both fields possible for issuelinks
            print(f"Issue links to: {issue['outwardIssue']['key']}")
            new_ak = issue['outwardIssue']['key']
            new_ak = str(new_ak)  #make string so can work with requests
        except:
            print(f"Issue links to: {issue['inwardIssue']['key']}")
            new_ak = issue['inwardIssue']['key']
            new_ak = str(new_ak)
			
        #post the linked stories to Notion
        try:
            post_to_table(new_ak, repo_name)
        except:
            print("Exception, issue with Notion GET call.")
            post_to_slack("Exception, issue with Notion.")

else:
    print(f'Issuetype: {issuetype}')
