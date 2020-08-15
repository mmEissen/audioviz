
.PHONY: clean
clean:
	-rm -rf dist

dist:
	poetry build

image.tar.gz:
	docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
	docker build -t audioviz .
