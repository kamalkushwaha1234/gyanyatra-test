from storages.backends.azure_storage import AzureStorage
import os

class AzurePrishniStorage(AzureStorage):
        account_name = os.environ.get('AZUREACCOUNTNAME')
        account_key = os.environ.get('AZUREACCOUNTKEY')
        expiration_secs = None
        AZURE_CUSTOM_DOMAIN = os.environ.get('AZURECUSTOMDOMAIN')


class AzureStaticStorage(AzurePrishniStorage):
        azure_container = os.environ.get('AZURESTATICCONTAINER') 
        STATIC_LOCATION = os.environ.get('AZURESTATICLOCATION')
        STATIC_URL = os.environ.get('AZURESTATICURL')

class AzureMediaStorage(AzurePrishniStorage):
        azure_container = os.environ.get('AZUREMEDIACONTAINER')
        MEDIA_LOCATION = os.environ.get('AZUREMEDIALOCATION')
        MEDIA_URL =  os.environ.get('AZUREMEDIAURL')
