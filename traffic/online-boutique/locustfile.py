#!/usr/bin/python

#
# Copyright 2018 Google LLC
# Modifications copyright 2026 Timon Roxard
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# Modified 2026 Timon Roxard : added --seed argument for reproducibility.
# Modified 2026 Timon Roxard : added --duration-minutes argument to configure
# the duration of a load shape cycle.


import random
from locust import FastHttpUser, TaskSet, between, events
from faker import Faker
import datetime
fake = Faker()

products = [
    '0PUK6V6EV0',
    '1YMWWN1N4O',
    '2ZYFJ3GM2N',
    '66VCHSJNUP',
    '6E92ZMYYFZ',
    '9SIQT8TOJO',
    'L9ECAV7KIM',
    'LS4PSXUNUM',
    'OLJCESPC7Z']

def index(loc):
    loc.client.get("/")

def setCurrency(loc):
    currencies = ['EUR', 'USD', 'JPY', 'CAD', 'GBP', 'TRY']
    loc.client.post("/setCurrency",
        {'currency_code': random.choice(currencies)})

def browseProduct(loc):
    loc.client.get("/product/" + random.choice(products))

def viewCart(loc):
    loc.client.get("/cart")

def addToCart(loc):
    product = random.choice(products)
    loc.client.get("/product/" + product)
    loc.client.post("/cart", {
        'product_id': product,
        'quantity': random.randint(1,10)})

def empty_cart(loc):
    loc.client.post('/cart/empty')

def checkout(loc):
    addToCart(loc)
    current_year = datetime.datetime.now().year+1
    loc.client.post("/cart/checkout", {
        'email': fake.email(),
        'street_address': fake.street_address(),
        'zip_code': fake.zipcode(),
        'city': fake.city(),
        'state': fake.state_abbr(),
        'country': fake.country(),
        'credit_card_number': fake.credit_card_number(card_type="visa"),
        'credit_card_expiration_month': random.randint(1, 12),
        'credit_card_expiration_year': random.randint(current_year, current_year + 70),
        'credit_card_cvv': f"{random.randint(100, 999)}",
    })

def logout(loc):
    loc.client.get('/logout')  


class UserBehavior(TaskSet):

    def on_start(self):
        index(self)

    tasks = {index: 1,
        setCurrency: 2,
        browseProduct: 10,
        addToCart: 2,
        viewCart: 3,
        checkout: 1}

class WebsiteUser(FastHttpUser):
    tasks = [UserBehavior]
    wait_time = between(1, 10)

@events.init_command_line_parser.add_listener
def add_arguments(parser, **kwargs):
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=24 * 60,
        help="Durée d'un cycle en minutes (défaut: 1440 = 24h réelles)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed pour la reproductibilité (défaut: 42)"
    )

@events.init.add_listener
def on_locust_init(environment, **kwargs):
    random.seed(environment.parsed_options.seed)
