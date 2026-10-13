# Disco de Teste Fortuna. Precisa do ps2dev (https://github.com/ps2dev/ps2dev)
# com PS2DEV e PS2SDK no ambiente. O resultado é disco-teste/fortuna-teste.iso.

EE_BIN = fortuna.elf
EE_OBJS = fortuna.o
EE_INCS += -I$(GSKIT)/include
EE_LDFLAGS += -L$(GSKIT)/lib
EE_LIBS = -lgskit -ldmakit -lpad -lpatches

GSKIT ?= $(PS2DEV)/gsKit
ISO = fortuna-teste.iso

all: $(ISO)

$(ISO): $(EE_BIN) SYSTEM.CNF
	$(EE_STRIP) --strip-debug $(EE_BIN)
	python3 -I ../tools/fazer_iso.py $@ --volume FORTUNA_TESTE \
		SYSTEM.CNF=SYSTEM.CNF \
		FRTN_026.10=$(EE_BIN) \
		MODULES/SIO2MAN.IRX=$(PS2SDK)/iop/irx/sio2man.irx \
		MODULES/PADMAN.IRX=$(PS2SDK)/iop/irx/padman.irx

clean:
	rm -f $(EE_BIN) $(EE_OBJS) $(ISO)

include $(PS2SDK)/samples/Makefile.pref
include $(PS2SDK)/samples/Makefile.eeglobal
