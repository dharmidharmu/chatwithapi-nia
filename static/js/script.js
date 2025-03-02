selected_gpt_name = "";
currentMode = "new";
current_gpt_id = "";
uploadedImageName = ""; 
deployed_model_names = [];
const maxTokens = 8000;

document.addEventListener('DOMContentLoaded', function () { 
    const newGptForm = document.getElementById('newGptForm');
    const gptNameInput = document.getElementById('gptName');
    //const gptName1Input = document.getElementById('gptName1');
    const streamResponsesCheckbox = document.getElementById('streamResponses');
    const gptDescriptionInput = document.getElementById('gptDescription');
    const gptInstructionsInput = document.getElementById('gptInstructions');
    const gptModalPopUp = document.getElementById('gptModalPopUp');
    const chatHistory = document.getElementById('chat-history'); 
    const gptRagCheckbox = document.getElementById('ragCheckbox');
    const closePopupBtn = document.getElementById('closePopup');
    const gptFileInput = document.getElementById("fileInput");
    const newGptModalLabel = document.getElementById('newGptModalLabel');
    const createGptButton = document.getElementById('createGptButton');
    const errorMessage = document.getElementById('errorMsg');
    const successMessage = document.getElementById('successMsg');
    const imageUploadButton = document.getElementById('image-upload');
    const submitButton = document.getElementsByClassName('submitButton');
    const loadingOverlay = document.getElementById("loading-overlay");
    const notifications = document.getElementById('notifications');
    const sendButton = document.getElementById('sendMessageButton'); 
    const messageInput = document.getElementById('userInput'); 
    const uploadedImageName = document.getElementById('uploadedImageName');
    const welcomeMessageDiv = document.getElementById('welcomeMessageDiv');
    const gptLoadedDiv = document.getElementById('gptLoadedDiv');
    const usecasesDiv = document.createElement('div');
    const configToggle = document.getElementById('config-toggle');
    const totalTokensDiv = document.getElementsByClassName('token-progress-text')

    // 1. Focus on Page Load or GPT Load
    window.addEventListener('load', () => {
        userInput.focus();
    });

    // 2. Handle Enter Key Press
    userInput.addEventListener("keyup", (event) => {
        if (event.key === "Enter") {
            if (!event.shiftKey) {
                event.preventDefault();
            
                // Prevent default form submission if applicable
                sendButton.click();     // Trigger the button's click event
            }
        }  
    }); 

    function convertMarkDownToHtml(markdownText){
        //return markDownConverter.makeHtml(text);
        let htmlContent = marked.parse(markdownText); // Convert Markdown to HTML
        hljs.highlightAll(); // Apply syntax highlighting if code exists
        return htmlContent;
    }

    function clearUploadedImageName(){
         // Clean up the image name
         uploadedImageName.style.display = 'none';
         uploadedImageName.innerText = "";
    }

    // Scroll to the bottom of the chat
    function scrollToUserInputBox() {
        chatHistory.scrollBy = userInput.scrollIntoView; // Scroll to the bottom of the chat
        userInput.focus();
    }

    // Show/Hide overlay
    function showLoadingOverlay() {
        loadingOverlay.style.display = "block";
    }
    
    function hideLoadingOverlay() {
        loadingOverlay.style.display = "none";
    }

    // Function to open the modal in "edit" mode
    function openModal(gpt, mode) {
        // Set the current mode to "edit" or "new"
        currentMode = mode;

        gptNameInput.value = gpt.name;
        gptDescriptionInput.value = gpt.description;
        gptInstructionsInput.value = gpt.instructions;
        gptRagCheckbox.checked = (""+gpt.use_rag === "true" ) ? true : false;
        current_gpt_id = gpt._id;

        $("#newGptModalLabel").text(currentMode === "edit" ? "Edit GPT": "New GPT");
        $(".submitButton").attr("id", current_gpt_id);

        // You might need to use a different method to show the modal if not using Bootstrap 
        $('#newGptModal').modal('show');
    }

    // Toggle file upload section visibility 
    gptRagCheckbox.addEventListener('change', function (event) {
        const fileUploadSection = document.getElementById('fileUploadSection');
        fileUploadSection.style.display = event.target.checked ? 'block' : 'none';
    });

    // Create GPT Event Handler
    createGptButton.addEventListener('click', function (event) {
        var emptyGpt = {
            name: "",
            description: "",
            instructions: "",
            use_rag: false
        }
        openModal(emptyGpt, "new"); 
    });

    // Close Popup Event Handler
    closePopupBtn.addEventListener('click', function (event) {
        $('#newGptModal').modal('hide');
    });

    // Handle form submission
    newGptForm.addEventListener('submit', async function (event) {
        event.preventDefault(); // Prevent default form submission

        if(currentMode === "edit"){
            current_gpt_id = $(".submitButton").attr("id");
        }

        // Get data from the form fields
        const gptId = current_gpt_id || "new"; // If editing, use the current GPT's ID; otherwise, use "new"
        const gptName = gptNameInput.value;
        const gptDescription = gptDescriptionInput.value;
        const gptInstructions = gptInstructionsInput.value;
        const gptUseRag = gptRagCheckbox.checked ? "True" : "False";

        // Create a FormData object
        const gptData = new FormData();

        if(currentMode === "new"){
            gptData.append("gpt", JSON.stringify({
                name: gptName,
                description: gptDescription,
                instructions: gptInstructions,
                use_rag: gptUseRag
            }));
        } else {
            gptData.append("gpt", JSON.stringify({
                _id: current_gpt_id,
                name: gptName,
                description: gptDescription,
                instructions: gptInstructions,
                use_rag: gptUseRag
            }));
        }
        
        // Get the file input and Append each file
        var files = gptFileInput.files;
        if(files.length > 0){
            for (let i = 0; i < files.length; i++) {
                gptData.append("files", files[i]); // Use 'files[]' if expecting an array on server
            }
        }
        else{
            const default_file = new Blob(["Dummy Content"], { type: "application/octet-stream" });
            gptData.append("files", default_file, "Dummy Content");
        }

        if($("#newGptModalLabel").text().indexOf("Edit") !== -1){
            currentMode === "edit";
            url = `/update_gpt/${current_gpt_id}/${gptName}`;
            method = 'PUT';
        }else {
            currentMode === "new";
            url = '/create_gpt';
            method = 'POST';
        }

        showLoadingOverlay(); // Show loading overlay

        // To update your fetch call to handle file uploads along with JSON data, you'll need to use FormData instead of JSON.stringify.
        // By not setting the Content-Type header, fetch will automatically handle it when sending FormData, including the necessary boundary
        fetch(url, { 
            method: method,
            body: gptData // Send the FormData object directly instead of using JSON.stringify when dealing with file uploads
        })
        .then(response => {
            // Handle the response from the backend
            if (response.ok) {
                // GPT created successfully, you can:
                // 1. Close the modal and reset the form
                $('#newGptModal').modal('hide');
                newGptForm.reset();

                // 2. Update the UI (e.g., add the new GPT to the sidebar) 
                displayGPTs();

                // 3. Display a success message
                var status = currentMode === "edit" ? 'GPT updated successfully!' : 'New GPT created successfully!';
                handleSuccess(status);
            } else {
                // Handle errors (e.g., display an error message)
                console.error('Error creating GPT');
                handleErrors(response);
            }
        })
        .catch(error => {
            // Handle network or other errors
            console.error('Error:', error);
            handleErrors('An error occurred. Please try again later.')
        });

        hideLoadingOverlay();
    });

    async function getUseCases(gpt){
        await fetch(`/usecases/${gpt._id}`)
        .then(response => {
            if (!response.ok) {
                handleErrors(response);
            }
            return response.json();
        }).then(data => {   
            console.log(data);
            if(!data.usecases){
                chatHistory.innerHTML = ''; 
            }
            else
            {
                const useCases = data.usecases;
                var system_message_prefix = "";
                var dataset = "";

                usecasesDiv.innerHTML = '';
                usecasesDiv.id = "usecaseButtons";

                // Create buttons for each use case
                for (var i = 0; i < useCases.length; i++) {
                    const useCase = useCases[i];
                    
                    if(useCase.name === "PREFIX"){
                        system_message_prefix = useCase.instructions;
                        continue;
                    }

                    if(useCase.name === "DATA_SET"){
                        dataset = useCase.instructions;
                        continue;
                    }
                        
                    const button = document.createElement('button');
                    button.textContent = useCase.name;
                    button.title = useCase.description;
                    button.id = useCase._id;
                    //$(button).attr("instructions", useCase.instructions);
                    button.classList.add('use-case-button', 'btn', 'btn-primary', 'btn-sm');

                    // Add event listener to handle button click
                    button.addEventListener('click', function() {
                        showLoadingOverlay();

                        usecasesDiv.querySelectorAll('.use-case-button').forEach(button => {
                            button.classList.remove('active');
                        });

                        button.classList.add('active');

                        //const clearGPTButton = document.querySelector('.clear-gpt-button');
                        //clearGPTButton.click(); // Clear the chat history
                        //alert(useCase._id);
                        fetch(`/update_instruction/${gpt._id}/${gpt.name}/${useCase._id}`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            }//,
                           // body: JSON.stringify({instructions: "USE_CASE: " + useCase.name + "\n" + (system_message_prefix + "\n" + dataset + "\n" +  useCase.instructions) })
                            
                            //body: {instructions: useCase.instructions}
                        })
                        .then(response => {
                            if (response.ok) {

                                // Instruction updated successfully
                                handleSuccess('Instruction updated successfully');

                                const currentGPTIdElement = $('.nav-link.active');

                                //loadChatHistory(); 
                                displayGPTs(); // Update UI after updating the instruction (system message)

                                // Save because after displayGPTs the value will be lost
                                current_gpt_id = gpt._id; 

                                // Update the active GPT to current GPT
                                $("a[id='"+gpt._id+"']").addClass("active");
                            } else {
                                handleErrors('Error updating instruction');
                            }
                        })
                        .catch(error => {
                            handleErrors('Error updating instruction:', error);
                        });

                        hideLoadingOverlay();
                    });

                    usecasesDiv.appendChild(button);
                }

                // Append the usecase buttons
                gptLoadedDiv.appendChild(usecasesDiv);
            }
        }).catch(error => {
            console.error('Fetch error:', error);
            handleErrors(response);
        });
    }

    async function displayGPTs() {
        fetch('/get_gpts')
            .then(response => {
                if (!response.ok) {
                    handleErrors(response);
                    //throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                const gpts = data.gpts;
                const historyList = document.getElementById('historyList');
                historyList.innerHTML = ''; 
       
                gpts.forEach(gpt => {
                    // Create a list item
                    const listItem = document.createElement('li');
                    listItem.className = 'nav-item'; // Apply Bootstrap's nav-item class
       
                    // Create a link element
                    const link = document.createElement('a');
                    link.className = 'nav-link'; // Apply Bootstrap's nav-link class
                    link.href = '#'; // You'll likely want to link to a specific chat view
                    //link.id = `${gpt.name}`;
                    link.id = `${gpt._id}`;
                    //link.textContent = `${gpt.name} - ${gpt.description}`;
                    link.textContent = `${gpt.description} (${gpt.name})`;
                    
                    // Add a click listener to the link (or list item)
                    // Add logic here to handle clicks on GPT history items, e.g.,
                    link.addEventListener('click', () => {

                        showLoadingOverlay(); // Show loading overlay

                        // - Store the selected GPT's ID
                        selected_gpt_name = `${gpt.description}`;
                        current_gpt_id = `${gpt._id}`;
                        
                        if(gpt.use_rag)
                            getUseCases(gpt);
                        else
                            usecasesDiv.innerHTML = '';
                        

                        errorMessage.style = "display:none"; // Clear the error message
                        successMessage.style = "display:none"; // Clear the success messages

                        $("#gptTitle").text("AI Assisant "+ selected_gpt_name);
                        $("#gptTitle").attr("gpt_id", current_gpt_id);
                        console.log("Clicked GPT:", selected_gpt_name); // You can access the gpt._id here

                        handleLoading();

                        // Based on selected GPT, clear and load the chat history
                        loadChatHistory(`${gpt._id}`, selected_gpt_name);
                        
                        // - Update the chat interface to load conversations for the selected GPT
                        // Remove 'active' class from previously selected GPT
                        const previousSelectedGPT = document.querySelector('.nav-link.active');
                        if (previousSelectedGPT) {
                            previousSelectedGPT.classList.remove('active');
                        }

                        // Add 'active' class to the clicked GPT
                        link.classList.add('active');
                        userInput.focus(); // Focus on the input field after selecting a GPT
                        
                        hideLoadingOverlay(); // Hide loading overlay
                    });

                    // Add Edit button
                    const editGPTButton = document.createElement('i');
                    editGPTButton.classList.add('fas', 'fa-edit', 'edit-gpt-button');
                    editGPTButton.title = "Edit the GPT";
                    editGPTButton.addEventListener('click', (event) => {
                        event.stopPropagation(); // Prevent link click from firing
                        openModal(gpt, "edit"); 
                    });
                    listItem.appendChild(editGPTButton); 

                    // Add Clear Conversations button
                    // const clearGPTButton = document.createElement('button');
                    // clearGPTButton.id = gpt._id;
                    // clearGPTButton.append($("<i class='fas fa-edit'></i>"));
                    // clearGPTButton.textContent = 'Clear';
                    // clearGPTButton.classList.add('secondary'); // Add Bootstrap classes for styling

                    // Add Delete GPT button
                    const clearGPTButton = document.createElement('i');
                    clearGPTButton.classList.add('fas', 'fa-eraser', 'clear-gpt-button');
                    clearGPTButton.id = gpt._id;
                    clearGPTButton.title = "Clear conversations in GPT";

                    clearGPTButton.addEventListener('click', (event) => {
                        event.stopPropagation(); // Prevent link click from firing
                        if (confirm("Are you sure you want to clear the chat history? This action cannot be undone.")) {
                            fetch(`/clear_chat_history/${gpt._id}/${gpt.name}`, {
                                method: 'PUT'
                            })
                            .then(response => {
                                if (response.ok) {
                                    // Chat history cleared successfully, update UI (clear chat history)
                                    chatHistory.innerHTML = '';
                                    handleSuccess('Chat history cleared successfully!');
                                } else {
                                    console.error('Error clearing chat history');
                                    chatHistory.innerHTML = '';
                                    handleErrors(response);
                                }
                            })
                            .catch(error => {
                                console.error('Error:', error);
                                handleErrors('An error occurred. Please try again later.');
                            });
                        }
                    });
                    listItem.appendChild(clearGPTButton); 

                    // Add Delete GPT button
                    const deleteGPTButton = document.createElement('i');
                    // Add Font Awesome classes
                    deleteGPTButton.classList.add('fas', 'fa-trash-alt', 'delete-gpt-button');
                    deleteGPTButton.id = gpt._id;
                    deleteGPTButton.title = "Delete the GPT";
                    
                    deleteGPTButton.addEventListener('click', (event) => {
                        event.stopPropagation(); // Prevent link click from firing
                        if (confirm("Are you sure you want to delete this GPT? This action cannot be undone.")) {
                            fetch(`/delete_gpt/${gpt._id}/${gpt.name}`, {
                                method: 'DELETE' 
                            })
                            .then(response => {
                                if (response.ok) {
                                    // GPT deleted successfully, update UI (clear history list)
                                    const historyList = document.getElementById('historyList');
                                    historyList.innerHTML = '';

                                    chatHistory.innerHTML = '';
                                    handleSuccess('GPT deleted successfully!');
                                    displayGPTs();
                                } else {
                                    console.error('Error deleting GPT');
                                    handleErrors(response);
                                }
                            })
                            .catch(error => {
                                console.error('Error:', error);
                                handleErrors('An error occurred. Please try again later.');
                            });
                        }
                    });
                    listItem.appendChild(deleteGPTButton); 
       
                    // Append the link to the list item and then the list item to the list
                    listItem.appendChild(link); 
                    historyList.appendChild(listItem);
                });
            })
            .catch(error => {
                console.error('Fetch error:', error);
                handleErrors(response);
            });
    }

    async function loadChatHistory(gpt_id, gpt_name){
        await fetch(`/chat_history/${gpt_id}/${gpt_name}`)
            .then(response => {
                if (!response.ok) {
                    console.log('Network response was not ok');
                    chatHistory.innerHTML = '';
                    handleErrors(response);
                }
                return response.json();
            })
            .then(data => {
                if(data.message && data.message === "No GPTs found"){
                    chatHistory.innerHTML = ''; 
                }
                else{
                    const chat_history = data.chat_history;
                    const chatHistory = document.getElementById('chat-history');
                    chatHistory.innerHTML = ''; 
           
                    chat_history.forEach(chat => {
                        create_chat_history(chat.role, chat.content);
                    });

                    handleSuccess("Chat History Loaded Successfully!");
                }
            })
            .catch(error => {
                console.error('Fetch error:', error);
                // Handle the error (e.g., display an error message to the user)
                handleErrors("Error while fetching chat history");
            });

        // Scroll to the bottom of the chat after loading
        scrollToUserInputBox();
    }

    async function loadDeployments(){
        showLoadingOverlay();

        if(deployed_model_names.length == 0){
            await fetch(`/deployedModels`)
            .then(response => {
                if (!response.ok) {
                    console.log('Network response was not ok');
                    handleErrors(response);
                }
                return response.json();
            })
            .then(data => {
                if(data.message && data.message === "No deployments found"){
                    deployed_model_names = [];
                    populateModelNames(gptNameInput, deployed_model_names);
                }
                else{
                    const model_deployments = data.model_deployments;
                    deployed_model_names = model_deployments; // store in global variable
                    populateModelNames(gptNameInput, deployed_model_names);
                    handleSuccess("Deployments Loaded Successfully!");
                }
            })
            .catch(error => {
                console.error('Fetch error:', error);
                handleErrors("Error while fetching Model Deployments");
            })
            .finally(() => {
                hideLoadingOverlay();
            });
        }
    }

    function populateModelNames(gptNameInput, deployed_model_names){
        if(deployed_model_names.length > 0){
            gptNameInput.innerHTML = '';
            deployed_model_names.forEach(model_name => {
                const option = document.createElement('option');
                option.text = model_name;
                option.value = model_name;
                gptNameInput.add(option);
            });
        }
        else{
            gptNameInput.innerHTML = '';
            const option = document.createElement('option');
            option.text = "No Models Found";
            option.value = "";
            gptNameInput.add(option);
        }
    }

    // Function to send a chat message (you'll need to update how you get the selected gpt_id)
    async function sendMessage(current_gpt_id, gpt_name, user_message, uploadedImage) {

        showLoadingOverlay(); // Show loading overlay

        if(user_message === "" || ""+user_message === "undefined" || ""+user_message === "null") {
            handleErrors("Please enter a message to send.");
        }   
        else {
            // Show loading indicator
            const sendLoadingIndicator = document.getElementById('sendLoadingIndicator');
            sendLoadingIndicator.style.display = 'inline-block';

            try {
                // 1. Display the user's message
                const userMessageElement = document.createElement('div');
                userMessageElement.classList.add("message", "user-message");

                if(user_message.indexOf("data:image/jpeg;base64") !== -1 || uploadedImage){
                    console.log(user_message);
                    
                    //const imageUrl = URL.createObjectURL(imageBlob);
                    const imageBox = document.createElement('img');
                    imageBox.width = 200;
                    imageBox.height = 200;
                    imageBox.alt = 'Image analysis result';
                    imageBox.src = uploadedImage ? URL.createObjectURL(uploadedImage) : user_message;
                    userMessageElement.appendChild(imageBox);

                    const imageMessageElement = document.createElement('div');
                    imageMessageElement.classList.add("message", "user-message");
                    imageMessageElement.innerHTML = user_message + ' ';
                    userMessageElement.appendChild(imageMessageElement);
                }
                else{
                    const formattedContent = user_message.replace(/\n/g, '<br>'); // To maintain the formatting sent by the model in the response
                    userMessageElement.innerHTML = formattedContent + ' '; // Add space for button
                }
                
                chatHistory.appendChild(userMessageElement);

                // Read the user message and image file
                const gptData = new FormData();
                gptData.append("user_message", user_message);  // Append user query

                const model_configuration = {
                    max_tokens: document.getElementById('max-tokens').value,
                    temperature: document.getElementById('temperature').value,
                    top_p: document.getElementById('top-p').value,
                    frequency_penalty: document.getElementById('frequency-penalty').value,
                    presence_penalty: document.getElementById('presence-penalty').value,
                };
                gptData.append("params", JSON.stringify(model_configuration));  // Append model configuration

                if (uploadedImage) {
                    gptData.append("uploadedImage", uploadedImage);  // Append the image file
                } 
                else{
                    const default_file = new Blob(["dummy"], { type: "application/octet-stream" });
                    gptData.append("uploadedImage", default_file, "dummy");
                }

                // 2. Send the message to the server
                const isStreamingResponse = streamResponsesCheckbox && streamResponsesCheckbox.checked ? true : false;
                const chatURL =  isStreamingResponse ? `/chat/stream/${current_gpt_id}/${gpt_name}` : `/chat/${current_gpt_id}/${gpt_name}`;

                // 2. Send the message to the server
                const response = await fetch(chatURL, {
                    method: 'POST',
                    body: gptData
                    // headers: {
                    //     'Content-Type': 'application/json'
                    // },
                    //body: JSON.stringify({ user_message: user_message })
                });

                if (!response.ok) {
                    handleErrors(response);
                    //throw new Error(`HTTP error! status: ${response.status}`);
                }
                else{
                    if(isStreamingResponse){
                        // Get the reader from the response body
                        const reader = response.body.getReader();
                        const decoder = new TextDecoder();
                        let aiMessageElement = document.createElement('div');
                        aiMessageElement.classList.add("message", "ai-message");
                        chatHistory.appendChild(aiMessageElement);

                        // Function to read the stream
                        async function readStream() {
                            let { done, value } = await reader.read();
                            while (!done) {
                                // Decode the chunk and append it to the message element
                                // const chunk = decoder.decode(value, { stream: true });
                                // aiMessageElement.innerHTML += chunk.replace(/\n/g, '<br>');

                                const chunk = decoder.decode(value, { stream: true });
                                model_response = convertMarkDownToHtml(chunk);
                                aiMessageElement.innerHTML += chunk.replace(/\n/g, '<br>');

                                // Read the next chunk
                                ({ done, value } = await reader.read());
                            }
                        }

                        // Start reading the stream
                        readStream().catch(error => {
                            console.error('Error reading stream:', error);
                        });
                    } 
                    else{
                       var data = await response.json();
                        console.log(data);
                        //data = JSON.parse(data);
                        console.log("AI Response:", data.response);
                        const total_tokens = data.total_tokens;
                        totalTokensDiv.text = `${total_tokens}/${maxTokens}`;
                        updateTokenProgress(total_tokens, maxTokens);
                        
                        // 3. Display the AI's response
                        const aiMessageElement = document.createElement('div');
                        aiMessageElement.classList.add("message", "ai-message");
            
                        // var formattedContent = data.response ? data.response.replace(/\n/g, '<br>'):''; // To maintain the formatting sent by the model in the response
                        // aiMessageElement.innerHTML = formattedContent  + ' '; // Add space for button
                        
                        var model_response = data.response ? data.response : 'No response from model'; 
                        model_response = convertMarkDownToHtml(model_response);
                        aiMessageElement.innerHTML = model_response;
                        chatHistory.appendChild(aiMessageElement);

                        // 4. Display follow-up questions (if any)
                        if (data.follow_up_questions && data.follow_up_questions.length > 0) {
                            console.log('Follow-up Questions:', data.follow_up_questions);
                            const followUpDiv = document.createElement('div');
                            followUpDiv.classList.add('follow-up-questions');
                            // followUpDiv.innerHTML = '<strong>Follow-up Questions:</strong><br>';

                            data.follow_up_questions.forEach((question) => {
                                const followUpButton = document.createElement('button');
                                followUpButton.innerHTML = question;
                                followUpButton.classList.add('btn', 'btn-sm', 'follow-up-button');
                                followUpButton.dataset.value = question;

                                // When clicked, insert the follow-up question into the input box
                                followUpButton.addEventListener('click', function() {
                                    const chatInput = document.getElementById('userInput'); // Ensure this element exists
                                    if (chatInput) {
                                        chatInput.value = followUpButton.dataset.value; // Set the button value into the input field
                                    } else {
                                        console.error('Chat input box not found.');
                                    }
                                });

                                followUpDiv.appendChild(followUpButton);
                            });

                            aiMessageElement.appendChild(followUpDiv);
                        } 
                    }
                }
            } catch (error) {
                console.error('Error sending message:', error);
                // Handle the error (e.g., display an error message in the chat)
            }
            finally {
                // Hide loading indicator 
                sendLoadingIndicator.style.display = 'none';
                clearUploadedImageName(); // Clear the uploaded image name
                scrollToUserInputBox(); // Scroll to the bottom of the chat after loading
            }
        }

        hideLoadingOverlay(); // Hide loading overlay
    }

    function create_chat_history(role, content){
        if(role === "user"){
            // Display the user's message
            const userMessageElement = document.createElement('div');
            userMessageElement.classList.add("message", "user-message");
            
            //if(content.indexOf("chatimages") !== -1){
            if(content.indexOf("data:image/jpeg;base64") !== -1){
                console.log(content);
                
                //const imageUrl = URL.createObjectURL(imageBlob);
                const imageBox = document.createElement('img');
                imageBox.width = 200;
                imageBox.height = 200;
                imageBox.alt = 'Image analysis result';
                imageBox.src = `${content}`;
                userMessageElement.appendChild(imageBox);
            }
            else if(content.indexOf("blob.core.windows.net") !== -1){
                console.log(content);
                
                //const imageUrl = URL.createObjectURL(imageBlob);
                const imageBox = document.createElement('img');
                imageBox.width = 250;
                imageBox.height = 200;
                imageBox.alt = `${content}`;
                imageBox.src = `${content}`;
                userMessageElement.appendChild(imageBox);
            }
            else{
                const formattedContent = content.replace(/\n/g, '<br>'); // To maintain the formatting sent by the model in the response
                userMessageElement.innerHTML = formattedContent + ' '; // Add space for button
                //userMessageElement.innerHTML = content + ' '; // Add space for button
            }

            chatHistory.appendChild(userMessageElement);
        }
        else if(role === "assistant"){
            // Display the AI's response
            const aiMessageElement = document.createElement('div');
            aiMessageElement.classList.add("message", "ai-message");

            // Replace newlines with <br> tags for HTML rendering
           // const formattedContent = content.replace(/\n/g, '<br>'); 
            aiMessageElement.innerHTML = convertMarkDownToHtml(content)  + ' '; // Add space for button
            

            //aiMessageElement.appendChild(aiDeleteButton);
            chatHistory.appendChild(aiMessageElement);
        }
    }

    // Image upload Event handler
    imageUploadButton.addEventListener("change", function(event) {
        const uploadedImage = event.target.files[0];
        if (uploadedImage) {
            console.log("Uploaded File:", uploadedImage);
            this.uploadedImage = uploadedImage;
            uploadedImageName.style.display = 'inline-block';
            uploadedImageName.innerText = uploadedImage.name;

            const showImage = document.createElement('img');
            showImage.width = 200;
            showImage.height = 200;
            showImage.alt = 'Uploaded Image';
            showImage.src = URL.createObjectURL(uploadedImage);
            uploadedImageName.appendChild(showImage);
        }
      });

    sendButton.addEventListener('click', (event) => {
        const user_message = messageInput.value;
        const currentGPTIdElement = $('.nav-link.active');
        event.preventDefault();

        clearUploadedImageName();

        if(currentGPTIdElement.length === 0){
            handleErrors("No GPT is selected. Please select a GPT to chat with.");
        }

        current_gpt_id = currentGPTIdElement.attr("id");

        // Sometime current_gpt_id may be not assigned, so double check and set it from the current chat window title
        if(current_gpt_id == undefined){
            current_gpt_id = $("#gptTitle").attr("gpt_id");
        }

         // Clear the input field after sending the message
        messageInput.value = ''; 
        const uploadedImage = imageUploadButton.files[0];  // Get the selected file

        if(selected_gpt_name === "" || ""+selected_gpt_name === "undefined" || ""+selected_gpt_name === "null"){
            errorMessage.innerHTML = 'No GPT is selected. Please select a GPT to chat with.';
        }else{
            console.log("Sending message to GPT:", selected_gpt_name + "User Message:" +user_message);
            sendMessage(current_gpt_id, selected_gpt_name, user_message, uploadedImage);
        }

        // Clear the uploaded image
        imageUploadButton.value = null;
    });

    const deleteAllGPTsButton = document.getElementById('deleteAllGPTsButton');
    deleteAllGPTsButton.addEventListener('click', function() {
        showLoadingOverlay(); // Show loading overlay

        if (confirm("Are you sure you want to delete all GPTs? This action cannot be undone.")) {
            fetch('/delete_all_gpts', {
                method: 'DELETE' 
            })
            .then(response => {
                if (response.ok) {
                    // GPTs deleted successfully, update UI (clear history list)
                    const historyList = document.getElementById('historyList');
                    historyList.innerHTML = ''; 

                    // Clear chat history
                    chatHistory.innerHTML = '';
                    $("#gptTitle").text("NIA");
                    
                    handleSuccess('All GPTs deleted successfully!');
                } else {
                    console.error('Error deleting GPTs');
                    handleErrors(response);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                handleErrors('An error occurred. Please try again later.')
            });
        } 
        
        hideLoadingOverlay();
    });

    const showLogsButton = document.getElementById('showLogs');
    showLogsButton.addEventListener('click', () => {
      fetch('/logs')
          .then(response => {
              if (!response.ok) {
                  handleErrors(response);
                  //throw new Error('Network response was not ok');
              }
              return response.json();
          })
          .then(data => {
              // Open logs in a new tab
              const newTab = window.open();
              newTab.document.body.innerHTML = `<pre>${data.log_content}</pre>`;
          })
          .catch(error => {
              console.error('Fetch error:', error);
              handleErrors("Error while fetching logs");
          });
    });

    // Update values when sliders are adjusted

    function updateSliderValues(sliderId, valueId){
        const slider = document.getElementById(sliderId);
        const valueDisplay = document.getElementById(valueId);

        slider.addEventListener('input', function() {
            valueDisplay.textContent = this.value;
        });
    }

    // Call the function for each slider:
    updateSliderValues('max-tokens', 'max-tokens-value');
    updateSliderValues('temperature', 'temperature-value');
    updateSliderValues('top-p', 'top-p-value');
    updateSliderValues('frequency-penalty', 'frequency-penalty-value');
    updateSliderValues('presence-penalty', 'presence-penalty-value');

    configToggle.addEventListener('click', function(event) {
        event.preventDefault();
        toggleConfigPanel();
    });
    
    // Update values when sliders are adjusted - START
    function toggleConfigPanel() {
        const configPanel = document.querySelector('.config-panel');
        configPanel.style.display = (configPanel.style.display === 'none') ? 'inline-flex' : 'none';
    }

    function handleSuccess(message) {
        if(message !== "" || ""+message !== "undefined" || ""+message !== "null") {
            successMessage.style.display = 'inline-block';
        
            successMessage.innerHTML = ''; // Clear the message
            successMessage.innerHTML = '<strong>NOTE:&nbsp;</strong>&nbsp;&nbsp;' + message;
        }

        hideLoadingOverlay(); // Hide loading overlay
    }

    // Function to handle errors from the backend
    function handleErrors(response) {
        
        if(typeof(response) === "string"){
            errorMessage.innerHTML = response.length > 0 ? response : "";
            errorMessage.style.display = response.length > 0 ? 'inline-block' : 'none';
        }
        else {
            errorMessage.style.display = 'inline-block';
            response.json().then(data => {
                const error = data.error;
                if (error) {
                    errorMessage.innerHTML = ''; // Clear the error message
                    errorMessage.innerHTML = '<strong>NOTE:&nbsp;</strong>&nbsp;&nbsp;' + error;
                    //errorMessage.append(error);
                }
            })
            .catch(error => {
                console.error('Error parsing response:', error);
                handleErrors('An error occurred while parsing the response.');
            });
        }

        hideLoadingOverlay(); // Hide loading overlay
        
        return false;
    }

    function handleLoading(){
        console.log("Current GPT : "+ selected_gpt_name);
        if(selected_gpt_name === "" || ""+selected_gpt_name === "undefined" || ""+selected_gpt_name === "null"){
            welcomeMessageDiv.style = "display:inline-block";
            gptLoadedDiv.style = "display:none";
        }else{
            welcomeMessageDiv.style = "display:none";
            gptLoadedDiv.style = "display:inline-block";
        }
    }

    // Clear error message on any button click event
    const contentContainer = document.getElementById('contentContainer');
    contentContainer.addEventListener('click', function () {
        // Handle button click event here
        successMessage.style.display = 'none';
        errorMessage.style.display = 'none';
    });

    function updateTokenProgress(tokensUsed, maxTokens) { // tokensUsed will come from your FastAPI backend
        const progressText = document.querySelector('.token-progress-text');
        progressText.textContent = `${tokensUsed}/${maxTokens}`;
    }

    // On load functions
    showLoadingOverlay();
    handleLoading();
    loadDeployments();
    displayGPTs();  // Call displayGPTs() to initially load the GPTs when the page loads.
    currentMode = "new"; // Set the current mode back to new
    scrollToUserInputBox();  // Scroll to the bottom of the chat after loading
    clearUploadedImageName();
    hideLoadingOverlay();
});
