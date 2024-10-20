def prepared_text_llama_response(messages):
  system_prompt, curr_user_dt = messages[0]['content'], messages[-1]['content']
  messages = messages[1:-1]

  if len(messages) % 2:
    messages = messages[:-1]

  initial_str = ""
  if len(messages) % 2 == 0 and len(messages) != 0:
    for idx in range(0, len(messages), 2):
      user_dt = messages[idx]['content']
      assistant_dt = messages[idx+1]['content']
      initial_str += f'''<|start_header_id|>user<|end_header_id|>\n\n{user_dt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n{assistant_dt}<|eot_id|>'''

  initial_str = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|>" + initial_str
  initial_str += f"<|start_header_id|>user<|end_header_id|>\n\n{curr_user_dt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
  return initial_str

  