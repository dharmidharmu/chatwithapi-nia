import os
import json
import logging
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

logger = logging.getLogger(__name__)

# Initialize the Azure OpenAI client
# client = AzureOpenAI(
#     azure_endpoint = os.getenv("AZURE_ENDPOINT_URL"), 
#     api_key=os.getenv("OPEN_API_KEY"),  
#     api_version=os.getenv("API_VERSION")

#     # azure_endpoint = os.getenv("GPT4O_ENDPOINT_URL"), 
#     # api_key=os.getenv("GPT4O_API_KEY"),  
#     # api_version=os.getenv("GPT4O_API_VERSION")
# )

# Define the deployment you want to use for your chat completions API calls

deployment_name = os.getenv("DEFAULT_MODEL_NAME")
# deployment_name = os.getenv("GPT4O_MODEL_NAME")

def run_conversation(client: AzureOpenAI, ticketNumber: str):
    messages = []
    
    ticket_conversation = get_conversation(ticketNumber)
    system_message = """You are a helpful AI Assistant."""
    user_prompt = get_user_prompt(ticket_conversation)

    # Initial user message
    messages.append({"role": "system", "content": system_message}) # Single function call
    messages.append({"role": "user", "content": user_prompt}) # Single function call


    # First API call: Ask the model to use the function
    response = client.chat.completions.create(
        model=deployment_name,
        messages=messages
    )

    # Process the model's response
    final_response = response.choices[0].message
    logger.info(f"Model's response: {final_response} \n Token Count: {response.usage.total_tokens}")  

    return final_response.content

ticket_conversations = {
                            "1" : """
                                    Kausik: Hello, I recently purchased the Samsung Cooler (AWCOOL121) and I'm experiencing some issues with it. The cooling seems to be low and the sound of the indoor unit is quite high. Can you help me with this?
                                    
                                    Lee Minh(Customer Support Executive): I'm sorry to hear that you're experiencing issues with your Samsung Cooler. I understand how frustrating that can be. Let's start by checking a few things. Have you ensured that the cooler is placed in a well-ventilated area and there's no obstruction around the unit?
                                    
                                    Kausik: Yes, I have made sure that the cooler has enough space around it for proper ventilation. The issue still persists.
                                    
                                    Lee Minh(Customer Support Executive): I see. In that case, it's possible that there may be an issue with the refrigerant levels or the compressor. Have you noticed any water leakage or ice buildup around the unit?
                                    
                                    Kausik: Actually, now that you mention it, I have noticed some water leakage around the unit. It's not a lot, but there's definitely some water pooling underneath the cooler.
                                    
                                    Lee Minh(Customer Support Executive): Thank you for sharing that information. The water leakage could indicate a potential issue with the condensate drain or the evaporator coil. It's best to have a technician inspect the unit to diagnose and resolve the problem. I'll schedule a service appointment for you at the earliest convenience.
                                    
                                    Kausik: I appreciate your help. Before we conclude, can you provide an estimate of the cost for any spare parts or service that may be required to fix the issues with the cooler?
                                    
                                    Lee Minh(Customer Support Executive): Absolutely, I can provide you with an estimate. The cost of spare parts and service will depend on the specific issue identified by the technician during the inspection. However, as a rough estimate, the cost for parts and service could range from $100 to $300, depending on the extent of the repairs needed. This includes potential costs for components such as the compressor, condensate drain, or evaporator coil.
                                    
                                    Kausik: Thank you for the information. I understand that the actual cost may vary based on the diagnosis. I look forward to the service appointment and hope that the issues with my Samsung Cooler can be resolved.
                                    
                                    Lee Minh(Customer Support Executive): You're welcome. We aim to provide as much clarity as possible regarding the potential costs involved. I've scheduled the appointment for you, and you should receive a confirmation email shortly. If you have any other questions or concerns, feel free to reach out to us. I'll also escalate this issue to our senior technical team for further review and resolution.
                                    
                                    Kausik: Thank you for your assistance. I will keep you updated on the outcome of the service appointment.
                                    
                                    Lee Minh(Customer Support Executive): You're welcome. I hope the technician is able to resolve the issues with your Samsung Cooler. If you need any further assistance, don't hesitate to contact us. Have a great day!
                                    
                                    Kausik: Thank you, you too. Goodbye.
                                    
                                    """, 
                            "2" : """
                                    Hi Kausik,
                                    \n
                                    Thanks for contacting. Could you please provide more details on from when you are facing the issue and also suggest a good time to have a phone call so that we can contact to assist on this issue better.
                                    \n
                                    \n
                                    Regards,
                                    \n
                                    K (Support Team)
                                    \n
                                    From: Kausik.HariharanLakshmiprabha@in.bosch.com
                                    Sent: November 20, 2024 01:15:35 PM
                                    To:cod.b2b.servicerequest@my349385.mail.crm.ondemand.com
                                    Subject: Issue with Product Samsung Cooler - AWCOOL121
                                    \n\n\n
                                    \n
                                    Hi Team,
                                    \n
                                    \n
                                    I have an issue with Product Samsung Cooler - AWCOOL121, where cooling is low and sound of the indoor unit is high.
                                    \n
                                    \n
                                    Kindly provide a solution to fine tune if possible, from my end or would require a technician to inspect the cooler.
                                    \n
                                    \n
                                    \n
                                    Mit freundlichen Grüßen / Best regards

                                    Kausik Hariharan Lakshmiprabha

                                    CRM & eCommerce (SX/BSV-TC3)
                                    Robert Bosch GmbH | Postfach 10 60 50 | 70049 Stuttgart | GERMANY | www.bosch.com
                                    Kausik.HariharanLakshmiprabha@in.bosch.com

                                    Registered Office: Stuttgart, Registration Court: Amtsgericht Stuttgart, HRB 14000;
                                    Chairman of the Supervisory Board: Prof. Dr. Stefan Asenkerschbaumer;
                                    Managing Directors: Dr. Stefan Hartung, Dr. Christian Fischer, Dr. Markus Forschner,
                                    Stefan Grosch, Dr. Markus Heyn, Dr. Frank Meyer, Katja von Raven, Dr. Tanja Rückert
                                    ​
                                    \n
                                    """,
                            "3" : """
                                From: John Doe john.doe@gmail.com
                                Sent: November 25, 2024, 9:00 AM
                                To: support@apple.com
                                Subject: Screen Flickering Issue with Apple M2 Pro Max

                                Dear Customer Support,

                                I have been facing an issue with my Apple M2 Pro Max laptop. The screen flickers excessively, especially when I edit videos using software like Final Cut Pro and Adobe Premiere Pro. This is disrupting my work, and I urgently need a resolution.

                                Could you please assist?

                                Thank you,
                                John Doe

                                From: Sarah Thompson support@apple.com
                                Sent: November 25, 2024, 11:30 AM
                                To: John Doe john.doe@gmail.com
                                Subject: Re: Screen Flickering Issue with Apple M2 Pro Max

                                Dear John Doe,

                                Thank you for reaching out to us. I am sorry to hear about the inconvenience caused by the flickering screen on your Apple M2 Pro Max. I completely understand how disruptive this can be, especially during video editing tasks.

                                To assist you better, could you please answer the following questions?

                                When did this issue start occurring?
                                Does the screen flicker only while editing videos, or do you notice it during other activities as well?
                                Have you tried any troubleshooting steps, such as updating your software or adjusting the screen refresh rate?
                                Is your laptop running the latest version of macOS?
                                Looking forward to your response so we can provide the best solution.

                                Best regards,
                                Sarah Thompson
                                Customer Support Team
                                Apple Support

                                From: John Doe john.doe@gmail.com
                                Sent: November 26, 2024, 8:15 AM
                                To: Sarah Thompson support@apple.com
                                Subject: Re: Screen Flickering Issue with Apple M2 Pro Max

                                Dear Sarah,

                                Thank you for your prompt response. Here are the answers to your questions:

                                The issue started about a week ago.
                                The screen flickers mainly during video editing. I haven't noticed it much during regular tasks like browsing.
                                I tried restarting the laptop and updating the video editing software, but the issue persists. I haven’t adjusted the refresh rate yet.
                                Yes, my laptop is running the latest version of macOS Ventura.
                                Please let me know how to proceed.

                                Best regards,
                                John Doe

                                From: Sarah Thompson support@apple.com
                                Sent: November 26, 2024, 10:45 AM
                                To: John Doe john.doe@gmail.com
                                Subject: Re: Screen Flickering Issue with Apple M2 Pro Max

                                Dear John Doe,

                                Thank you for providing the details. Based on the information you shared, it seems the issue could be related to either the graphics driver or a potential hardware fault in the display. Here are the next steps:

                                Adjust the screen refresh rate by navigating to System Settings > Displays and selecting a lower refresh rate. Test if this resolves the flickering.
                                If the issue persists, we recommend reinstalling the graphics driver. You can do this by visiting the Apple Support page and downloading the relevant drivers for your model.
                                If neither of these solutions resolves the issue, we can arrange for a technician to inspect your laptop. Alternatively, you can initiate a return or repair request. If you choose this option, kindly let us know your preferred course of action.

                                We look forward to hearing from you.

                                Best regards,
                                Sarah Thompson
                                Customer Support Team
                                Apple Support

                                From: John Doe john.doe@gmail.com
                                Sent: November 27, 2024, 9:00 AM
                                To: Sarah Thompson support@apple.com
                                Subject: Re: Screen Flickering Issue with Apple M2 Pro Max

                                Dear Sarah,

                                Thank you for the suggested steps. I tried adjusting the refresh rate and reinstalling the graphics driver, but unfortunately, the issue still persists. I would like to proceed with a technician visit to inspect the device.

                                Please let me know the next steps to arrange this.

                                Best regards,
                                John Doe

                                From: Sarah Thompson support@apple.com
                                Sent: November 27, 2024, 12:15 PM
                                To: John Doe john.doe@gmail.com
                                Subject: Re: Screen Flickering Issue with Apple M2 Pro Max

                                Dear John Doe,

                                Thank you for trying the troubleshooting steps. I’m sorry to hear that the issue still persists. I’ve arranged for a technician to visit and inspect your device. You will receive an email shortly with the appointment details and further instructions.

                                If you have any additional concerns or questions in the meantime, please don’t hesitate to reach out.

                                Best regards,
                                Sarah Thompson
                                Customer Support Team
                                Apple Support
                                  """,
                            "4" : """
                                    From: Michael Smith michael.smith@gmail.com
                                    Sent: November 26, 2024, 10:00 AM
                                    To: support@apple.com
                                    Subject: Concern About Authenticity of iPhone 15 Pro

                                    Dear Customer Support,

                                    I recently purchased an iPhone 15 Pro, but it doesn't feel like an original product. Some features seem off, and the performance is slower than expected. Could you please help verify its authenticity?

                                    Thank you,
                                    Michael Smith

                                    From: Sarah Thompson support@apple.com
                                    Sent: November 26, 2024, 12:15 PM
                                    To: Michael Smith michael.smith@gmail.com
                                    Subject: Re: Concern About Authenticity of iPhone 15 Pro

                                    Dear Michael,

                                    Thank you for reaching out. I’m sorry to hear about your concerns. To help verify the authenticity of your iPhone, could you provide the following details?

                                    The device serial number (found in Settings > General > About).
                                    Proof of purchase.
                                    Any specific features or issues that seem unusual.
                                    Looking forward to your reply.

                                    Best regards,
                                    Sarah Thompson
                                    Customer Support Team
                                    Apple Support

                                    From: Michael Smith michael.smith@gmail.com
                                    Sent: November 26, 2024, 3:00 PM
                                    To: Sarah Thompson support@apple.com
                                    Subject: Re: Concern About Authenticity of iPhone 15 Pro

                                    Dear Sarah,

                                    Thanks for responding. Here are the details:

                                    Serial number: GX12345XYZ.
                                    Proof of purchase is attached to this email.
                                    The display feels unresponsive at times, Face ID struggles to work, and the battery life is unusually short.
                                    Please let me know what can be done.

                                    Best regards,
                                    Michael Smith

                                    From: Sarah Thompson support@apple.com
                                    Sent: November 26, 2024, 5:00 PM
                                    To: Michael Smith michael.smith@gmail.com
                                    Subject: Re: Concern About Authenticity of iPhone 15 Pro

                                    Dear Michael,

                                    Thank you for sharing the details. Based on the serial number, the device doesn’t match Apple’s database. It may not be genuine. I recommend visiting your nearest Apple Store to confirm. You may also reach out to your seller for a refund or replacement.

                                    Please let us know if you need further assistance.

                                    Best regards,
                                    Sarah Thompson
                                    Customer Support Team
                                    Apple Support

                                    From: Michael Smith michael.smith@gmail.com
                                    Sent: November 27, 2024, 8:00 AM
                                    To: Sarah Thompson support@apple.com
                                    Subject: Re: Concern About Authenticity of iPhone 15 Pro

                                    Dear Sarah,

                                    Thank you for the clarification. I’ll visit the Apple Store to verify this and contact the seller if needed.

                                    Appreciate your help.

                                    Best regards,
                                    Michael Smith
                                  """,
                            "5" : """
                                    From: Priya Sharma priya.sharma@gmail.com
                                    Sent: November 26, 2024, 9:30 AM
                                    To: support@bosch.com
                                    Subject: Damaged Water Sprayer in Bosch Dishwasher DSHWHR2024

                                    Dear Customer Support,

                                    I’ve noticed that the water sprayer in my Bosch dishwasher (Model: DSHWHR2024) is damaged, and it’s affecting the cleaning performance. Could you please guide me on how to resolve this issue?

                                    Thank you,
                                    Priya Sharma

                                    From: Rohan Mehta support@bosch.com
                                    Sent: November 26, 2024, 11:15 AM
                                    To: Priya Sharma priya.sharma@gmail.com
                                    Subject: Re: Damaged Water Sprayer in Bosch Dishwasher DSHWHR2024

                                    Dear Priya,

                                    Thank you for reaching out. I’m sorry to hear about the damaged sprayer. Could you confirm:

                                    When the issue started?
                                    If you’ve noticed any cracks or visible damage?
                                    The purchase date or warranty details?
                                    This will help us suggest the best solution.

                                    Best regards,
                                    Rohan Mehta
                                    Customer Support Team
                                    Bosch Appliances

                                    From: Priya Sharma priya.sharma@gmail.com
                                    Sent: November 26, 2024, 2:00 PM
                                    To: Rohan Mehta support@bosch.com
                                    Subject: Re: Damaged Water Sprayer in Bosch Dishwasher DSHWHR2024

                                    Dear Rohan,

                                    Here’s the requested information:

                                    The issue started two weeks ago.
                                    There’s a visible crack in the sprayer.
                                    I purchased the dishwasher in January 2024, and it’s still under warranty.
                                    Please let me know how to proceed.

                                    Best regards,
                                    Priya Sharma

                                    From: Rohan Mehta support@bosch.com
                                    Sent: November 26, 2024, 5:00 PM
                                    To: Priya Sharma priya.sharma@gmail.com
                                    Subject: Re: Damaged Water Sprayer in Bosch Dishwasher DSHWHR2024

                                    Dear Priya,

                                    Thank you for the details. Since the sprayer is under warranty, we’ll replace it at no cost. A technician will contact you shortly to schedule the repair.

                                    If you have further concerns, feel free to reach out.

                                    Best regards,
                                    Rohan Mehta
                                    Customer Support Team
                                    Bosch Appliances

                                    From: Priya Sharma priya.sharma@gmail.com
                                    Sent: November 27, 2024, 8:30 AM
                                    To: Rohan Mehta support@bosch.com
                                    Subject: Re: Damaged Water Sprayer in Bosch Dishwasher DSHWHR2024

                                    Dear Rohan,

                                    Thank you for the quick response and support. I’ll wait for the technician’s call. Appreciate your help.

                                    Best regards,
                                    Priya Sharma

                                  """,

                                  "882":"""
                                    <p>Dear Kausik,</p>\n<p style=\"font-family: 'verdana,geneva'; font-size: 11pt;\">Thank you for confirming your pickup time. Your item will be ready for collection at the security office during the scheduled time. Just a reminder, please bring a valid photo ID for identity verification.</p>\n<p>If you are unable to collect the item at the arranged time or need to reschedule, let us know, and we will be happy to accommodate.</p>\n<p style=\"font-family: 'verdana,geneva'; font-size: 11pt;\">Regards,</p>\n<p style=\"font-family: 'verdana,geneva'; font-size: 11pt;\">Muhammed,</p>\n<p style=\"font-family: 'verdana,geneva'; font-size: 11pt;\">Security Team - Dubai Mall A</p>\n<p style=\"border: none; border-top: solid #bfbfbf 1px !important; padding: 5px 0px 0px 0px; font-size: 11px; font-family: Calibri,sans-serif; color: #1f497d;\"><strong>From: </strong>kausik.hariharanlakshmiprabha@in.bosch.com<br /><strong>Sent: </strong>November 27, 2024 02:57:07 PM<br /><strong>To:</strong>cod.b2b.servicerequest@my349385.mail.crm.ondemand.com<br /><strong>Subject: </strong>RE: [ Ticket: 882 ] Lost Item - Bottle in Dubai Mall A</p>\n<style><!--\n/* Font Definitions */\n@font-face\n\t{font-family:\"Cambria Math\";\n\tpanose-1:2 4 5 3 5 4 6 3 2 4;}\n@font-face\n\t{font-family:Calibri;\n\tpanose-1:2 15 5 2 2 2 4 3 2 4;}\n@font-face\n\t{font-family:Verdana;\n\tpanose-1:2 11 6 4 3 5 4 4 2 4;}\n@font-face\n\t{font-family:inherit;}\n@font-face\n\t{font-family:\"verdana\\,geneva\";\n\tpanose-1:0 0 0 0 0 0 0 0 0 0;}\n/* Style Definitions */\np.MsoNormal, li.MsoNormal, div.MsoNormal\n\t{margin:0in;\n\tfont-size:11.0pt;\n\tfont-family:\"Calibri\",sans-serif;\n\tmso-ligatures:standardcontextual;}\na:link, span.MsoHyperlink\n\t{mso-style-priority:99;\n\tcolor:#0563C1;\n\ttext-decoration:underline;}\nspan.EmailStyle23\n\t{mso-style-type:personal-compose;\n\tfont-family:\"Arial\",sans-serif;\n\tcolor:windowtext;\n\tfont-weight:normal;\n\tfont-style:normal;}\n.MsoChpDefault\n\t{mso-style-type:export-only;}\n@page WordSection1\n\t{size:8.5in 11.0in;\n\tmargin:1.0in 1.0in 1.0in 1.0in;}\ndiv.WordSection1\n\t{page:WordSection1;}\n--></style>\n<!-- [if gte mso 9]><xml>\n<o:shapedefaults v:ext=\"edit\" spidmax=\"1026\" />\n</xml><![endif]--><!-- [if gte mso 9]><xml>\n<o:shapelayout v:ext=\"edit\">\n<o:idmap v:ext=\"edit\" data=\"1\" />\n</o:shapelayout></xml><![endif]-->\n<div class=\"WordSection1\">\n<p class=\"MsoNormal\" style=\"mso-margin-top-alt: auto; mso-margin-bottom-alt: auto;\"><span style=\"mso-ligatures: none;\">Dear Muhammed,</span></p>\n<p class=\"MsoNormal\" style=\"mso-margin-top-alt: auto; mso-margin-bottom-alt: auto;\"><span style=\"mso-ligatures: none;\">Thank you so much for the good news! I am relieved to hear that my item has been found.</span></p>\n<p class=\"MsoNormal\" style=\"mso-margin-top-alt: auto; mso-margin-bottom-alt: auto;\"><span style=\"mso-ligatures: none;\">I will be able to pick it up tomorrow, 28.11.2024 between 1 PM to 3 PM. Please let me know if I need to bring anything else apart from my ID for verification.</span></p>\n<p class=\"MsoNormal\" style=\"mso-margin-top-alt: auto; mso-margin-bottom-alt: auto;\"><span style=\"mso-ligatures: none;\">Thanks again for your assistance!</span></p>\n<p class=\"MsoNormal\"><span style=\"font-size: 10.0pt; font-family: 'Arial',sans-serif;\">&nbsp;</span></p>\n<p class=\"MsoNormal\"><span style=\"font-size: 10.0pt; font-family: 'Arial',sans-serif; color: black; mso-ligatures: none;\">Mit freundlichen Gr&uuml;&szlig;en / Best regards <br /><br /><strong>Kausik Hariharan Lakshmiprabha <br />SX/BSV-TC3 </strong></span><span style=\"mso-ligatures: none;\"><br />​ </span></p>\n<div style=\"border: none; border-top: solid #E1E1E1 1.0pt; padding: 3.0pt 0in 0in 0in;\">\n<p class=\"MsoNormal\"><strong><span style=\"mso-ligatures: none;\">From:</span></strong><span style=\"mso-ligatures: none;\"> cod.b2b.servicerequest@my349385.mail.crm.ondemand.com &lt;cod.b2b.servicerequest@my349385.mail.crm.ondemand.com&gt; <br /><strong>Sent:</strong> Wednesday, November 27, 2024 2:56 PM<br /><strong>To:</strong> Hariharan Lakshmiprabha Kausik (SDS/BSV-ES1) &lt;kausik.hariharanlakshmiprabha@in.bosch.com&gt;<br /><strong>Subject:</strong> Re: [ Ticket: 882 ] Lost Item - Bottle in Dubai Mall A</span></p>\n</div>\n<p class=\"MsoNormal\">&nbsp;</p>\n<p><span style=\"font-family: 'verdana,geneva',serif;\">&nbsp;</span></p>\n<p>Dear Kausik,</p>\n<p>We have some good news! After checking our records and reviewing the areas you mentioned, your lost item&mdash;a IKEA Bottle&mdash;has been turned in to our security office. It is now available for pickup.</p>\n<p>You can collect your item from the security office located at Dubai Mall A during business hours 8.00 AM to 6 PM . Please bring a valid photo ID for identity verification before we hand over your item.</p>\n<p>Thank you for your patience, and we look forward to assisting you with the pickup.</p>\n<p><span style=\"font-family: 'verdana,geneva',serif;\">Regards,</span></p>\n<p><span style=\"font-family: 'verdana,geneva',serif;\">Muhammed,</span></p>\n<p><span style=\"font-family: 'verdana,geneva',serif;\">Mall Security Team, Dubai Mall A</span></p>\n<div style=\"mso-element: para-border-div; border: none; border-top: solid #BFBFBF 1.0pt; padding: 4.0pt 0in 0in 0in;\">\n<p style=\"border: none; padding: 0in;\"><strong><span style=\"font-size: 8.5pt; font-family: 'Calibri',sans-serif; color: #1f497d;\">From: </span></strong><span style=\"font-size: 8.5pt; color: #1f497d;\"><a href=\"mailto:kausik.hariharanlakshmiprabha@in.bosch.com\" target=\"_blank\" rel=\"noopener\">kausik.hariharanlakshmiprabha@in.bosch.com</a><br /><strong><span style=\"font-family: 'Calibri',sans-serif;\">Sent: </span></strong>November 27, 2024 02:53:40 PM<br /><strong><span style=\"font-family: 'Calibri',sans-serif;\">To:</span></strong>cod.b2b.servicerequest@my349385.mail.crm.ondemand.com<br /><strong><span style=\"font-family: 'Calibri',sans-serif;\">Subject: </span></strong>RE: [ Ticket: 882 ] Lost Item - Bottle in Dubai Mall A</span></p>\n</div>\n<p class=\"MsoNormal\" style=\"mso-margin-top-alt: auto; mso-margin-bottom-alt: auto;\"><span style=\"mso-ligatures: none;\">Dear Muhammed,</span></p>\n<p class=\"MsoNormal\" style=\"mso-margin-top-alt: auto; mso-margin-bottom-alt: auto;\"><span style=\"mso-ligatures: none;\">Thank you for the update. I appreciate your prompt attention to this matter. I understand that it may take some time to check the lost and found records and areas, so I&rsquo;ll await your response.</span></p>\n<p class=\"MsoNormal\" style=\"mso-margin-top-alt: auto; mso-margin-bottom-alt: auto;\"><span style=\"mso-ligatures: none;\">Please let me know if I need to provide any additional information.</span></p>\n<p class=\"MsoNormal\"><span style=\"font-size: 10.0pt; font-family: 'Arial',sans-serif;\">&nbsp;</span></p>\n<p class=\"MsoNormal\"><span style=\"font-size: 10.0pt; font-family: 'Arial',sans-serif;\">&nbsp;</span></p>\n<p class=\"MsoNormal\"><span style=\"font-size: 10.0pt; font-family: 'Arial',sans-serif; color: black; mso-ligatures: none;\">Mit freundlichen Gr&uuml;&szlig;en / Best regards <br /><br /><strong><span style=\"font-family: 'Arial',sans-serif;\">Kausik Hariharan Lakshmiprabha </span></strong><br /><br />CRM &amp; eCommerce (SX/BSV-TC3) <br />Robert Bosch GmbH | Postfach 10 60 50 | 70049 Stuttgart | <span style=\"text-transform: uppercase;\"> GERMANY | </span><a href=\"www.bosch.com\" target=\"_blank\" rel=\"noopener\"><span style=\"color: blue;\">www.bosch.com</span></a> <br /><a href=\"mailto:Kausik.HariharanLakshmiprabha@in.bosch.com\" target=\"_blank\" rel=\"noopener\"><span style=\"color: blue;\">Kausik.HariharanLakshmiprabha@in.bosch.com</span></a> </span><span style=\"font-size: 8.0pt; font-family: 'Arial',sans-serif; color: black; mso-ligatures: none;\"><br /><br />Registered Office: Stuttgart, Registration Court: Amtsgericht Stuttgart, HRB 14000; <br />Chairman of the Supervisory Board: Prof. Dr. Stefan Asenkerschbaumer; <br />Managing Directors: Dr. Stefan Hartung, Dr. Christian Fischer, Dr. Markus Forschner, <br />Stefan Grosch, Dr. Markus Heyn, Dr. Frank Meyer, Katja von Raven, Dr. Tanja R&uuml;ckert </span><span style=\"mso-ligatures: none;\"><br />​ </span></p>\n<div style=\"border: none; border-top: solid #E1E1E1 1.0pt; padding: 3.0pt 0in 0in 0in;\">\n<p class=\"MsoNormal\"><strong><span style=\"font-family: 'Calibri',sans-serif; mso-ligatures: none;\">From:</span></strong><span style=\"mso-ligatures: none;\"> <a href=\"mailto:cod.b2b.servicerequest@my349385.mail.crm.ondemand.com\" target=\"_blank\" rel=\"noopener\">cod.b2b.servicerequest@my349385.mail.crm.ondemand.com</a> &lt;<a href=\"mailto:cod.b2b.servicerequest@my349385.mail.crm.ondemand.com\" target=\"_blank\" rel=\"noopener\">cod.b2b.servicerequest@my349385.mail.crm.ondemand.com</a>&gt; <br /><strong><span style=\"font-family: 'Calibri',sans-serif;\">Sent:</span></strong> Wednesday, November 27, 2024 2:53 PM<br /><strong><span style=\"font-family: 'Calibri',sans-serif;\">To:</span></strong> Hariharan Lakshmiprabha Kausik (SDS/BSV-ES1) &lt;<a href=\"mailto:kausik.hariharanlakshmiprabha@in.bosch.com\" target=\"_blank\" rel=\"noopener\">kausik.hariharanlakshmiprabha@in.bosch.com</a>&gt;<br /><strong><span style=\"font-family: 'Calibri',sans-serif;\">Subject:</span></strong> Re: [ Ticket: 882 ] Lost Item - Bottle in Dubai Mall A</span></p>\n</div>\n<p class=\"MsoNormal\">&nbsp;</p>\n<p><span style=\"font-family: 'Verdana',sans-serif;\">Dear Kausik,</span></p>\n<p>This is Muhammed from Dubai Mall A's security team. We have received your inquiry and are currently reviewing our lost and found records.</p>\n<p>We will check the area you mentioned, as well as other possible locations where the item might have been turned in. We will let you know if we find the item.</p>\n<p>Thank you for your patience, and we will contact you as soon as we have any updates.</p>\n<p><span style=\"font-family: 'verdana,geneva',serif;\">Regards,</span></p>\n<p><span style=\"font-family: 'verdana,geneva',serif;\">Muhammed,</span></p>\n<p><span style=\"font-family: 'verdana,geneva',serif;\">Mall Security Team, Dubai Mall A</span></p>\n<div style=\"border: none; border-top: solid #BFBFBF 1.0pt; padding: 4.0pt 0in 0in 0in;\">\n<p><strong><span style=\"font-size: 8.5pt; font-family: 'Calibri',sans-serif; color: #1f497d;\">From: </span></strong><span style=\"font-size: 8.5pt; color: #1f497d;\"><a href=\"mailto:kausik.hariharanlakshmiprabha@in.bosch.com\" target=\"_blank\" rel=\"noopener\">kausik.hariharanlakshmiprabha@in.bosch.com</a><br /><strong><span style=\"font-family: 'Calibri',sans-serif;\">Sent: </span></strong>November 27, 2024 02:51:20 PM<br /><strong><span style=\"font-family: 'Calibri',sans-serif;\">To:</span></strong>cod.b2b.servicerequest@my349385.mail.crm.ondemand.com<br /><strong><span style=\"font-family: 'Calibri',sans-serif;\">Subject: </span></strong>RE: [ Ticket: 882 ] Lost Item - Bottle in Dubai Mall A</span></p>\n</div>\n<p class=\"MsoNormal\"><span style=\"font-size: 10.0pt; font-family: 'Arial',sans-serif;\">Dear Alex,</span></p>\n<p class=\"MsoNormal\" style=\"mso-margin-top-alt: auto; mso-margin-bottom-alt: auto;\"><span style=\"mso-ligatures: none;\">Thank you for your quick response and for forwarding my request to the security team. I appreciate your help and will await their follow-up.</span></p>\n<p class=\"MsoNormal\" style=\"mso-margin-top-alt: auto; mso-margin-bottom-alt: auto;\"><span style=\"mso-ligatures: none;\">Please keep me posted on any updates and let me know if I need to provide further details to assist in locating the item.</span></p>\n<p class=\"MsoNormal\"><span style=\"font-size: 10.0pt; font-family: 'Arial',sans-serif;\">&nbsp;</span></p>\n<p class=\"MsoNormal\"><span style=\"font-size: 10.0pt; font-family: 'Arial',sans-serif; color: black; mso-ligatures: none;\">Mit freundlichen Gr&uuml;&szlig;en / Best regards <br /><br /><strong><span style=\"font-family: 'Arial',sans-serif;\">Kausik Hariharan Lakshmiprabha </span></strong><strong><br /><strong><span style=\"font-family: 'Arial',sans-serif;\">SX/BSV-TC3 </span></strong></strong></span><span style=\"mso-ligatures: none;\"><br />​ </span></p>\n<div style=\"border: none; border-top: solid #E1E1E1 1.0pt; padding: 3.0pt 0in 0in 0in;\">\n<p class=\"MsoNormal\"><strong><span style=\"font-family: 'Calibri',sans-serif; mso-ligatures: none;\">From:</span></strong><span style=\"mso-ligatures: none;\"> <a href=\"mailto:cod.b2b.servicerequest@my349385.mail.crm.ondemand.com\" target=\"_blank\" rel=\"noopener\"> cod.b2b.servicerequest@my349385.mail.crm.ondemand.com</a> &lt;<a href=\"mailto:cod.b2b.servicerequest@my349385.mail.crm.ondemand.com\" target=\"_blank\" rel=\"noopener\">cod.b2b.servicerequest@my349385.mail.crm.ondemand.com</a>&gt; <br /><strong><span style=\"font-family: 'Calibri',sans-serif;\">Sent:</span></strong> Wednesday, November 27, 2024 2:50 PM<br /><strong><span style=\"font-family: 'Calibri',sans-serif;\">To:</span></strong> Hariharan Lakshmiprabha Kausik (SDS/BSV-ES1) &lt;<a href=\"mailto:kausik.hariharanlakshmiprabha@in.bosch.com\" target=\"_blank\" rel=\"noopener\">kausik.hariharanlakshmiprabha@in.bosch.com</a>&gt;<br /><strong><span style=\"font-family: 'Calibri',sans-serif;\">Subject:</span></strong> Re: [ Ticket: 882 ] Lost Item - Bottle in Dubai Mall A</span></p>\n</div>\n<p class=\"MsoNormal\">&nbsp;</p>\n<p><span style=\"font-family: 'Verdana',sans-serif;\">Dear Kausik,</span></p>\n<p>Thank you for reaching out to us. We are sorry to hear about the item you lost while visiting our mall. We understand how frustrating this can be and are here to help.</p>\n<p>We have forwarded your request to our security team, as they are responsible for monitoring and maintaining the lost and found items in the mall. Our security team will check if the item has been turned in, and they will contact you with any updates.</p>\n<p>In the meantime, please feel free to reach out to us if you have any additional information or questions.</p>\n<p><span style=\"font-size: 14.0pt; font-family: inherit;\">Regards,</span></p>\n<p><span style=\"font-size: 14.0pt; font-family: inherit;\">Alex,</span></p>\n<p><span style=\"font-size: 14.0pt; font-family: inherit;\">Support Executive - Dub Mall A</span></p>\n<div style=\"border: none; border-top: solid #BFBFBF 1.0pt; padding: 4.0pt 0in 0in 0in;\">\n<p><strong><span style=\"font-size: 8.5pt; font-family: 'Calibri',sans-serif; color: #1f497d;\">From: </span></strong><span style=\"font-size: 8.5pt; color: #1f497d;\"><a href=\"mailto:Kausik.HariharanLakshmiprabha@in.bosch.com\" target=\"_blank\" rel=\"noopener\">Kausik.HariharanLakshmiprabha@in.bosch.com</a><br /><strong><span style=\"font-family: 'Calibri',sans-serif;\">Sent: </span></strong>November 27, 2024 02:46:44 PM<br /><strong><span style=\"font-family: 'Calibri',sans-serif;\">To:</span></strong>cod.b2b.servicerequest@my349385.mail.crm.ondemand.com<br /><strong><span style=\"font-family: 'Calibri',sans-serif;\">Subject: </span></strong>Lost Item - Bottle in Dubai Mall A</span></p>\n</div>\n<p class=\"MsoNormal\"><span style=\"font-size: 10.0pt; font-family: 'Arial',sans-serif;\">Hello,</span></p>\n<p class=\"MsoNormal\"><span style=\"font-size: 10.0pt; font-family: 'Arial',sans-serif;\">&nbsp;</span></p>\n<p class=\"MsoNormal\">I am writing to report that I have lost an item while shopping at Dubai Mall A on 26.11.2024. The item is a Blue sports bottle from IKEA.</p>\n<p class=\"MsoNormal\">&nbsp;</p>\n<p class=\"MsoNormal\">I believe I may have lost it in the Food court, but I am unsure of the exact area. I would greatly appreciate it if you could help me locate it or check with your lost and found department.</p>\n<p class=\"MsoNormal\"><span style=\"font-size: 10.0pt; font-family: 'Arial',sans-serif;\">&nbsp;</span></p>\n<p class=\"MsoNormal\"><span style=\"font-size: 10.0pt; font-family: 'Arial',sans-serif; color: black; mso-ligatures: none;\">Mit freundlichen Gr&uuml;&szlig;en / Best regards <br /><br /><strong><span style=\"font-family: 'Arial',sans-serif;\">Kausik Hariharan Lakshmiprabha </span></strong><strong><br /><strong><span style=\"font-family: 'Arial',sans-serif;\">SX/BSV-TC3 </span></strong></strong></span><span style=\"mso-ligatures: none;\"><br />​ </span></p>\n</div>
                                  """,

                                  "883": """
                                    كاوسيك: مرحبًا، لقد فقدت زجاجة رياضية زرقاء من أيكيا أثناء تسوقي في دبي مول (أ) يوم 26 نوفمبر 2024. هل يمكنكم مساعدتي؟
                                    أليكس (دعم العملاء): مرحبًا كاوسيك، أنا آسف لسماع ذلك. سأقوم بإحالة طلبك إلى فريق الأمن الذي يتولى مراقبة الأشياء المفقودة والموجودة. سنبقيك على اطلاع بأي تحديث.
                                    محمد (فريق الأمن): مرحبًا كاوسيك، لدينا زجاجتك هنا في مكتب الأمن. يمكنك القدوم لاستلامها.
                                    كاوسيك: شكرًا جزيلاً! سأأتي غدًا بين الساعة 1 ظهرًا و3 عصرًا. هل أحتاج إلى إحضار أي شيء آخر غير بطاقة الهوية للتحقق؟
                                    محمد: لا، فقط تأكد من إحضار بطاقة هوية صالحة. إذا لم تتمكن من الحضور في الوقت المحدد، أخبرنا وسنعمل على تحديد موعد آخر يناسبك.
                                    كاوسيك: رائع، شكرًا لكم! سأراكم غدًا.                                        
                                    """,

                                    "884": """
                                    考西克: 你好，我在2024年11月26日在迪拜购物中心A购物时丢失了一只宜家的蓝色运动水瓶。你们能帮我找一下吗？
                                    亚历克斯（客户支持）： 你好，考西克，很抱歉听到你的物品丢失了。我会将你的请求转交给负责失物招领的安保团队，我们会随时向你更新进展。
                                    穆罕默德（安保团队）： 你好，考西克，我们找到了你的水瓶。它现在在安保办公室，可以来领取了。
                                    考西克: 太好了！谢谢你！我明天下午1点到3点之间过来取。除了身份证验证外，还需要带其他东西吗？
                                    穆罕默德: 不需要，只要带上有效的身份证就可以。如果你明天不能按时来，请告诉我们，我们可以为你调整时间。
                                    考西克: 好的，谢谢！明天见。                                   
                                    """
                       }

def get_user_prompt(ticket_conversation: str):

    # user_prompt = f"""Read through the ticket summary below enclosed within triple backticks (```) and extract the content with key "Text" and summarize the conversation in it. If the same conversation is repeated ignore. 
    #                 After a careful analysis of the conversation, always provide the following information in valid json format only. 
    #                 - a title for the summary. Include the ticket number (title), 
    #                 - issue description (description), 
    #                 - important questions asked (questions), 
    #                 - the summary capturing the highlights of the conversation (summary),
    #                 - resolution provided, if any (resolution)
    #                 - next steps, if any within 6 words maximum (next_steps)
    #                     ```{ticket_conversation}```

    #                 Sometimes there can be empty or irrelevant conversations. In such cases, provide a message stating that the conversation is irrelevant or empty.
    #                 """

    user_prompt = f"""Read through the ticket summary below enclosed within triple backticks (```) and extract the content with key "Text" and summarize the conversation in it. If the same conversation is repeated ignore. 
                    After a careful analysis of the conversation, always provide the following information in valid json format only. 
                    - a title for the summary. Include the ticket number (title), 
                    - the summary capturing the highlights of the conversation (summary),
                    - the next steps identified from the conversation (next_steps)
                        ```{ticket_conversation}```

                    Sometimes there can be empty or irrelevant conversations. In such cases, provide a message stating that the conversation is irrelevant or empty.
                    Always translate the conversation to English before summarizing.
                    """
    
    return user_prompt

def get_conversation(ticketNumber: str):
    if ticketNumber in ticket_conversations:
        ticket_conversation = ticket_conversations[ticketNumber]
    else:
        ticket_conversation = "No conversation found for the given ticket number. Please try again with a valid ticket"

    logger.info(f"Ticket Conversation is {ticket_conversation}")
    
    return ticket_conversation

# Run the conversation and print the result
#print(run_conversation("44"))

