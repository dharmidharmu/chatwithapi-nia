import openai


chat_completion = {
    "id": "d344051d-b928-459a-b452-32caeb85d8c7",
    "choices": [
        {
            "finish_reason": "stop",
            "index": 0,
            "logprobs": None,
            "message": {
                "content": "The retrieved documents do not contain any information regarding users' opinions or reviews of a 4K web camera. The requested information is not available in the retrieved data. Please try another query or topic.",
                "refusal": None,
                "role": "assistant",
                "function_call": None,
                "tool_calls": None,
                "end_turn": True,
                "context": {
                    "citations": [
                        {
                            "content": "P015\nTablet\n10.5-inch display, 4GB RAM, 64GB storage, and up to 10 hours of battery life.\nTablets\n4\n12-19-2022\nOR00129\nSamsung\n249\n400\n01-02-2023\nDelivered\n475-682-4976\nYes\n30.0\nJacob Thomas\n12345\njacob.thomas@hotmail.com\n187-654-3210\nGermany\n31\n9 Hauptplatz, Berlin\n22 Lindengasse, Munich\n4.0\nThe size is ideal for reading, browsing the web, and watching videos. It's lightweight and portable, great for taking on the go.\npositive\nCredit Card\nSuccess",
                            "title": None,
                            "url": None,
                            "filepath": None,
                            "chunk_id": "0"
                        },
                        {
                            "content": "P015\nTablet\n10.5-inch display, 4GB RAM, 64GB storage, and up to 10 hours of battery life.\nTablets\n1\n11-20-2022\nOR00171\nSamsung\n249\n100\n11-27-2022\nCancelled\n327-164-8702\nNo\n10\nMia Thompson\n12345\nmia.thompson@yahoo.com\n198-765-4321\nGermany\n31\n9 Hauptplatz, Berlin\n22 Lindengasse, Munich\n4.0\nThe size is ideal for reading, browsing the web, and watching videos. It's lightweight and portable, great for taking on the go.\npositive\nCredit Card\nSuccess",
                            "title": None,
                            "url": None,
                            "filepath": None,
                            "chunk_id": "0"
                        },
                        {
                            "content": "P015\nTablet\n10.5-inch display, 4GB RAM, 64GB storage, and up to 10 hours of battery life.\nTablets\n5\n03-16-2022\nOR00111\nSamsung\n249\n500\n03-31-2022\nProcessing\n402-212-7513\nYes\n30.0\nAndrew Johnson\n12345\nandrew.johnson@yahoo.com\n176-543-2109\nGermany\n31\n9 Hauptplatz, Berlin\n22 Lindengasse, Munich\n4.0\nThe size is ideal for reading, browsing the web, and watching videos. It's lightweight and portable, great for taking on the go.\npositive\nCredit Card\nSuccess",
                            "title": None,
                            "url": None,
                            "filepath": None,
                            "chunk_id": "0"
                        },
                        {
                            "content": "P015\nTablet\n10.5-inch display, 4GB RAM, 64GB storage, and up to 10 hours of battery life.\nTablets\n1\n08-22-2022\nOR00132\nSamsung\n249\n100\n09-02-2022\nDelivered\n408-628-5884\nNo\n10\nEmma Jackson\n12345\nemma.jackson@gmail.com\n154-321-7890\nGermany\n31\n9 Hauptplatz, Berlin\n22 Lindengasse, Munich\n4.0\nThe size is ideal for reading, browsing the web, and watching videos. It's lightweight and portable, great for taking on the go.\npositive\nCredit Card\nSuccess",
                            "title": None,
                            "url": None,
                            "filepath": None,
                            "chunk_id": "0"
                        },
                        {
                            "content": "P015\nTablet\n10.5-inch display, 4GB RAM, 64GB storage, and up to 10 hours of battery life.\nTablets\n5\n06-12-2022\nOR00073\nSamsung\n249\n500\n06-18-2022\nProcessing\n452-120-7168\nNo\n10\nAva Harris\n12345\nava.harris@hotmail.com\n190-876-5432\nGermany\n31\n9 Hauptplatz, Berlin\n22 Lindengasse, Munich\n4.0\nA solid tablet for a reasonable price. It offers a good balance of performance, features, and portability.\nneutral\nCredit Card\nSuccess",
                            "title": None,
                            "url": None,
                            "filepath": None,
                            "chunk_id": "0"
                        },
                        {
                            "content": "P015\nTablet\n10.5-inch display, 4GB RAM, 64GB storage, and up to 10 hours of battery life.\nTablets\n4\n12-24-2022\nOR00095\nSamsung\n249\n400\n01-02-2023\nDelivered\n396-376-5157\nNo\n10\nSarah Wilson\n12345\nsarah.wilson@hotmail.com\n178-905-4321\nGermany\n31\n9 Hauptplatz, Berlin\n22 Lindengasse, Munich\n4.0\nA solid tablet for a reasonable price. It offers a good balance of performance, features, and portability.\nneutral\nCredit Card\nSuccess",
                            "title": None,
                            "url": None,
                            "filepath": None,
                            "chunk_id": "0"
                        },
                        {
                            "content": "P021\nHeadphones\nOver-ear design, 40mm drivers, wired connection, and adjustable headband.\nAudio\n5\n12-11-2022\nOR00128\nBeats\n199\n500\n12-18-2022\nDelivered\n327-181-1453\nYes\n30.0\nEmily Smith\n12345\nemily.smith@gmail.com\n198-765-4321\nItaly\n34\n123 Via Veneto, Rome\n66 Via Garibaldi, Milan\n4.0\nA great pair of headphones with excellent sound quality and a comfortable fit.  Good value for the price.\nneutral\nDebit Card\nSuccess",
                            "title": None,
                            "url": None,
                            "filepath": None,
                            "chunk_id": "0"
                        },
                        {
                            "content": "P124\nMechanical Keyboard\nRGB backlighting, tactile switches, anti-ghosting, and customizable key mapping.\nAccessories\n5\n01-11-2022\nOR00164\nCorsair\n120\n500\n01-24-2022\nReturn in Transit\n332-121-2779\nNo\n10\nAndrew Johnson\n12345\nandrew.johnson@yahoo.com\n176-543-2109\nJapan\n28\n56 Akihabara St, Tokyo\n12 Shinjuku Blvd, Yokohama\n4.0\nA good mechanical keyboard with a decent price. The tactile feedback and RGB lighting are nice features.\nneutral\nNet Banking\nSuccess",
                            "title": None,
                            "url": None,
                            "filepath": None,
                            "chunk_id": "0"
                        },
                        {
                            "content": "P003\nMechanical Keyboard\nRGB backlighting, tactile switches, anti-ghosting, and customizable key mapping.\nAccessories\n1\n07-10-2024\nOR00003\nCorsair\n120\n100\n07-14-2024\nIn Transit\n1122334455\nNo\n10\nMichael Brown\n12345\nmichael.brown@gmail.com\n187-654-3210\nJapan\n28\n56 Akihabara St, Tokyo\n12 Shinjuku Blvd, Yokohama\n4.0\nA good mechanical keyboard with a decent price. The tactile feedback and RGB lighting are nice features.\nneutral\nNet Banking\nSuccess",
                            "title": None,
                            "url": None,
                            "filepath": None,
                            "chunk_id": "0"
                        },
                        {
                            "content": "P015\n4K Webcam\n4K resolution, autofocus, built-in microphone, and plug-and-play USB interface.\nAccessories\n2\n11-03-2022\nOR00141\nLogitech\n150\n200\n11-17-2022\nCancelled\n527-535-7307\nNo\n10\nLaura Williams\n12345\nlaura.williams@yahoo.com\n154-321-7890\nUnited Kingdom\n35\n28 Oxford St, London\n63 King Rd, Manchester\n4.5\nThis 4K webcam delivers stunning clarity for video calls.  The picture quality is a significant upgrade, and the autofocus is quick and accurate.\npositive\nDebit Card\nSuccess",
                            "title": None,
                            "url": None,
                            "filepath": None,
                            "chunk_id": "0"
                        }
                    ],
                    "intent": '["What are the reviews of 4K web cameras?", "What is the best 4K web camera according to customer reviews?", "What are the features of 4K web cameras?", "What are the pros and cons of 4K web cameras?", "What are the top-rated 4K web cameras?", "What is the price range of 4K web cameras?"]'
                }
            }
        }
    ],
    "created": 1730966171,
    "model": "gpt-35-turbo",
    "object": "extensions.chat.completion",
    "service_tier": None,
    "system_fingerprint": None,
    "usage": {
        "completion_tokens": 119,
        "prompt_tokens": 5222,
        "total_tokens": 5341
    }
}
