How to use

`docker build -t minerva-flask:latest .`

```bash
docker run -it --rm `
>>   --name minerva-dev `
>>   -p 5000:5000 `
>>   -v ${PWD}:/app `
>>   minerva-flask:latest `
>>   flask run --host=0.0.0.0 --debug
```