from typing import List
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId

class Order(BaseModel):
    _id: str
    product_id: str
    product_description: str
    product_specification: str
    product_category: str
    qty: str
    order_date: datetime
    order_id: str
    brand: str
    price: int
    order_total: int
    delivery_date: datetime
    status: str
    agent_contact_number: str
    return_policy: str
    return_days: str
    user_name: str
    password: str
    email: str
    phone_number: str
    country: str
    age: int
    shipping_address: List[str] = []
    customer_rating: str
    customer_reviews: List[str] = []
    review_sentiment: str
    payment_method: str
    payment_status: str
   

    

