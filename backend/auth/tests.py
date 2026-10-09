# auth/tests.py
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
import json

class LoginTest(TestCase):
    token = None  # Variable de clase para almacenar el token

    def setUp(self):
        # Crea un usuari de prova per al test
        self.username = 'customers'
        self.password = 'customers'
        self.user = User.objects.create_user(username=self.username, password=self.password)

    def test_login(self):
        print('test_login: ', self)
        # URL de login (canvia-ho si has personalitzat la URL de login)
        login_url = reverse('login')
        
        # Dades de login
        data = {
            'username': self.username,
            'password': self.password,
        }
        
        # Fa una petició POST amb les dades de login
        response = self.client.post(login_url, data)
        
        # Comprova si s'ha redirigit a la pàgina d'inici de sessió correctament (200 OK)
        self.assertEqual(response.status_code, 200)
        
        # print(response.content.decode('utf-8')) # {"username":"usuari_de_prova","token":"7b21d0b21ac28cd8721688b5db7d484adc32101f","tenants":[]}

        # Verificar la presència del token en la resposta
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertIn('token', response_data)
        
        # Obtindre el valor del token
        received_token = response_data.get('token')
        print(received_token)
        self.__class__.token = received_token

    def test_token(self):
        print('test_token: ', self)
    
        if self.__class__.token is None:
            self.fail("No se encontró ningún token guardado")
        
        print(self.__class__.token)
        
