#ifndef __dvb_demux_h
#define __dvb_demux_h

#include <aio.h>
#include <lib/dvb/idvb.h>
#include <lib/dvb/idemux.h>
#include <lib/dvb/pvrparse.h>
#include "filepush.h"
#ifdef HAVE_RASPBERRYPI
#include <lib/dvb/edvbdemux.h>
#else
class eDVBDemux: public iDVBDemux
{
	DECLARE_REF(eDVBDemux);
public:
	enum {
		evtFlush
	};
	eDVBDemux(int adapter, int demux);
	virtual ~eDVBDemux();

	RESULT setSourceFrontend(int fenum);
	int getSource() { return source; }
	RESULT setSourcePVR(int pvrnum);
	int getDvrId() { return m_dvr_id; }

	RESULT createSectionReader(eMainloop *context, ePtr<iDVBSectionReader> &reader);
	RESULT createPESReader(eMainloop *context, ePtr<iDVBPESReader> &reader);
	RESULT createTSRecorder(ePtr<iDVBTSRecorder> &recorder, unsigned int packetsize = 188, bool streaming=false);
	RESULT getMPEGDecoder(ePtr<iTSMPEGDecoder> &reader, int index);
	RESULT getSTC(pts_t &pts, int num);
	RESULT getCADemuxID(uint8_t &id) { id = demux; return 0; }
	RESULT getCAAdapterID(uint8_t &id) { id = adapter; return 0; }
	RESULT flush();
#if SIGCXX_MAJOR_VERSION == 3
	RESULT connectEvent(const sigc::slot<void(int)> &event, ePtr<eConnection> &conn);
#else
	RESULT connectEvent(const sigc::slot1<void,int> &event, ePtr<eConnection> &conn);
#endif
	int openDVR(int flags);

	int getRefCount() { return ref; }
//	RESULT setCaDescr(ca_descr_t *ca_descr, bool initial);
//	RESULT setCaPid(ca_pid_t *ca_pid);
//	bool decrypt(uint8_t *data, int len, int &packetsCount);
private:
	int adapter, demux, source;
//	cDeCSA *decsa;
	int m_dvr_busy;
	int m_dvr_id;
	int m_dvr_source_offset;
	friend class eDVBSectionReader;
	friend class eDVBPESReader;
	friend class eDVBAudio;
	friend class eDVBVideo;
	friend class eDVBPCR;
	friend class eDVBTText;
	friend class eDVBTSRecorder;
	friend class eDVBCAService;
	friend class eTSMPEGDecoder;
#ifdef HAVE_AMLOGIC
	int m_pvr_fd;
	friend class eAMLTSMPEGDecoder;
#endif
#if SIGCXX_MAJOR_VERSION == 3
	sigc::signal<void(int)> m_event;
#else
	sigc::signal1<void, int> m_event;
#endif
	int openDemux(void);
};
#endif
class eDVBSectionReader: public iDVBSectionReader, public sigc::trackable
{
	DECLARE_REF(eDVBSectionReader);
	int fd;
#if SIGCXX_MAJOR_VERSION == 3
	sigc::signal<void(const uint8_t*)> read;
#else
	sigc::signal1<void, const uint8_t*> read;
#endif
	ePtr<eDVBDemux> demux;
	int active;
	int checkcrc;
	void data(int);
	ePtr<eSocketNotifier> notifier;
public:
	eDVBSectionReader(eDVBDemux *demux, eMainloop *context, RESULT &res);
	virtual ~eDVBSectionReader();
	RESULT setBufferSize(int size);
	RESULT start(const eDVBSectionFilterMask &mask);
	RESULT stop();
#if SIGCXX_MAJOR_VERSION == 3
	RESULT connectRead(const sigc::slot<void(const uint8_t*)> &read, ePtr<eConnection> &conn);
#else
	RESULT connectRead(const sigc::slot1<void,const uint8_t*> &read, ePtr<eConnection> &conn);
#endif
};

class eDVBPESReader: public iDVBPESReader, public sigc::trackable
{
	DECLARE_REF(eDVBPESReader);
	int m_fd;
#if SIGCXX_MAJOR_VERSION == 3
	sigc::signal<void(const uint8_t*, int)> m_read;
#else
	sigc::signal2<void, const uint8_t*, int> m_read;
#endif
	ePtr<eDVBDemux> m_demux;
	int m_active;
	void data(int);
	ePtr<eSocketNotifier> m_notifier;
public:
	eDVBPESReader(eDVBDemux *demux, eMainloop *context, RESULT &res);
	virtual ~eDVBPESReader();
	RESULT setBufferSize(int size);
	RESULT start(int pid);
	RESULT stop();
#if SIGCXX_MAJOR_VERSION == 3
	RESULT connectRead(const sigc::slot<void(const uint8_t*,int)> &read, ePtr<eConnection> &conn);
#else
	RESULT connectRead(const sigc::slot2<void,const uint8_t*, int> &read, ePtr<eConnection> &conn);
#endif
};

class eDVBRecordFileThread: public eFilePushThreadRecorder
{
public:
	eDVBRecordFileThread(int packetsize, int bufferCount, int buffersize = -1, bool sync_mode = false);
	~eDVBRecordFileThread();
	void setTimingPID(int pid, iDVBTSRecorder::timing_pid_type pidtype, int streamtype);
	void startSaveMetaInformation(const std::string &filename);
	void stopSaveMetaInformation();
	int getLastPTS(pts_t &pts);
	int getFirstPTS(pts_t &pts);
	void setTargetFD(int fd) { m_fd_dest = fd; }
	void enableAccessPoints(bool enable) { m_ts_parser.enableAccessPoints(enable); }
protected:
	int asyncWrite(int len);
	/* override */ int writeData(int len);
	/* override */ void flush();

	struct AsyncIO
	{
		struct aiocb aio;
		unsigned char* buffer;
		AsyncIO()
		{
			memset(&aio, 0, sizeof(aiocb));
			buffer = NULL;
		}
		int wait();
		int start(int fd, off_t offset, size_t nbytes, void* buffer);
		int poll(); // returns 1 if busy, 0 if ready, <0 on error return
		int cancel(int fd); // returns <0 on error, 0 cancelled, >0 bytes written?
	};
	eMPEGStreamParserTS m_ts_parser;
	off_t m_current_offset;
	int m_fd_dest;
	bool m_sync_mode;
	typedef std::vector<AsyncIO> AsyncIOvector;
	unsigned char* m_allocated_buffer;
	AsyncIOvector m_aio;
	AsyncIOvector::iterator m_current_buffer;
	std::vector<int> m_buffer_use_histogram;
};

class eDVBRecordStreamThread: public eDVBRecordFileThread
{
public:
	eDVBRecordStreamThread(int packetsize, int buffersize = -1, bool sync_mode = false);

protected:
	int writeData(int len);
	void flush();
};

class eDVBTSRecorder: public iDVBTSRecorder, public sigc::trackable
{
	DECLARE_REF(eDVBTSRecorder);
public:
	eDVBTSRecorder(eDVBDemux *demux, int packetsize, bool streaming);
	~eDVBTSRecorder();

	RESULT setBufferSize(int size);
	RESULT start();
	RESULT addPID(int pid);
	RESULT removePID(int pid);

	RESULT setTimingPID(int pid, timing_pid_type pidtype, int streamtype);

	RESULT setTargetFD(int fd);
	RESULT setTargetFilename(const std::string& filename);
	RESULT setBoundary(off_t max);
	RESULT enableAccessPoints(bool enable);

	RESULT stop();

	RESULT getCurrentPCR(pts_t &pcr);
	RESULT getFirstPTS(pts_t &pts);

#if SIGCXX_MAJOR_VERSION == 3
	RESULT connectEvent(const sigc::slot<void(int)> &event, ePtr<eConnection> &conn);
#else
	RESULT connectEvent(const sigc::slot1<void,int> &event, ePtr<eConnection> &conn);
#endif
private:
	RESULT startPID(int pid);
	void stopPID(int pid);

	void filepushEvent(int event);

	std::map<int,int> m_pids;
#if SIGCXX_MAJOR_VERSION == 3
	sigc::signal<void(int)> m_event;
#else
	sigc::signal1<void,int> m_event;
#endif

	ePtr<eDVBDemux> m_demux;

	int m_running;
	int m_target_fd;
	int m_source_fd;
	eDVBRecordFileThread *m_thread;
	std::string m_target_filename;
	int m_packetsize;
	friend class eRTSPStreamClient;
};

#endif
