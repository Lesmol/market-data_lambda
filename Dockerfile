FROM public.ecr.aws/lambda/python:3.14-x86_64

COPY app.py ${LAMBDA_TASK_ROOT}

CMD [ "app.handler" ]