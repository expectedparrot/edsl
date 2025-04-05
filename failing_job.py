# from edsl import QuestionMultipleChoice, Model

# m = Model("test", canned_response= "1")

# q = QuestionMultipleChoice(
#     question_name = "example",
#     question_text = "What is 1+1?",
#     question_options = [1,2,3,4]
# )


# m2 = Model("test", canned_response= "Boo!")

# r = q.by(m2).run(disable_remote_inference=True, stop_on_exception=True)
# print(r.select("example"))

#r = q.run()
#r.select("example")


from edsl import QuestionMultipleChoice

q = QuestionMultipleChoice(
    question_name = "example",
    question_text = "What is 1+1?",
    question_options = [1,2,3,4]
)

r = q.run()
r.select("example")

#r = q.run()
#r.select("example")