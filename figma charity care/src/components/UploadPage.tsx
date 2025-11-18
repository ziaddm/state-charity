import { useState, useCallback } from 'react';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Alert, AlertDescription } from './ui/alert';
import { Building2, Upload, FileText, CheckCircle2, XCircle, AlertCircle, LogOut } from 'lucide-react';
import { Badge } from './ui/badge';

interface UploadPageProps {
  onLogout: () => void;
}

interface FileResult {
  id: string;
  fileName: string;
  status: 'pass' | 'error' | 'warning';
  message: string;
  details?: string[];
  uploadedAt: Date;
}

export default function UploadPage({ onLogout }: UploadPageProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [results, setResults] = useState<FileResult[]>([]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const validateFile = (file: File): FileResult => {
    const validExtensions = ['.pdf', '.xlsx', '.xls', '.csv', '.xml'];
    const maxSize = 10 * 1024 * 1024; // 10MB
    const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    
    // Mock validation logic
    if (!validExtensions.includes(fileExtension)) {
      return {
        id: Math.random().toString(36).substring(7),
        fileName: file.name,
        status: 'error',
        message: 'Invalid file format',
        details: [`Accepted formats: ${validExtensions.join(', ')}`],
        uploadedAt: new Date()
      };
    }

    if (file.size > maxSize) {
      return {
        id: Math.random().toString(36).substring(7),
        fileName: file.name,
        status: 'error',
        message: 'File size exceeds limit',
        details: ['Maximum file size: 10MB'],
        uploadedAt: new Date()
      };
    }

    // Simulate random validation results for demo
    const random = Math.random();
    
    if (random > 0.7) {
      return {
        id: Math.random().toString(36).substring(7),
        fileName: file.name,
        status: 'pass',
        message: 'File validated successfully',
        details: [
          'All required fields present',
          'Data format correct',
          'Patient records: ' + Math.floor(Math.random() * 100 + 50)
        ],
        uploadedAt: new Date()
      };
    } else if (random > 0.4) {
      return {
        id: Math.random().toString(36).substring(7),
        fileName: file.name,
        status: 'warning',
        message: 'File uploaded with warnings',
        details: [
          'Missing optional field: Secondary Insurance',
          'Date format inconsistency in row 15',
          'Processed with warnings'
        ],
        uploadedAt: new Date()
      };
    } else {
      return {
        id: Math.random().toString(36).substring(7),
        fileName: file.name,
        status: 'error',
        message: 'Validation failed',
        details: [
          'Missing required field: Patient ID in row 8',
          'Invalid income value in row 12',
          'Duplicate entry found in row 23'
        ],
        uploadedAt: new Date()
      };
    }
  };

  const processFiles = async (files: File[]) => {
    setIsUploading(true);
    
    // Simulate upload delay
    await new Promise(resolve => setTimeout(resolve, 1500));
    
    const newResults = files.map(file => validateFile(file));
    setResults(prev => [...newResults, ...prev]);
    setIsUploading(false);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      processFiles(files);
    }
  }, []);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      processFiles(files);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pass':
        return <CheckCircle2 className="w-5 h-5 text-green-600" />;
      case 'warning':
        return <AlertCircle className="w-5 h-5 text-amber-600" />;
      case 'error':
        return <XCircle className="w-5 h-5 text-red-600" />;
      default:
        return null;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pass':
        return 'bg-green-50 border-green-200';
      case 'warning':
        return 'bg-amber-50 border-amber-200';
      case 'error':
        return 'bg-red-50 border-red-200';
      default:
        return '';
    }
  };

  const stats = {
    total: results.length,
    passed: results.filter(r => r.status === 'pass').length,
    warnings: results.filter(r => r.status === 'warning').length,
    errors: results.filter(r => r.status === 'error').length
  };

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-10 h-10 bg-blue-600 rounded-lg">
                <Building2 className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-slate-900">Charity Care Portal</h1>
                <p className="text-slate-600">File Submission System</p>
              </div>
            </div>
            <Button 
              variant="outline" 
              onClick={onLogout}
              className="border-slate-300"
            >
              <LogOut className="w-4 h-4 mr-2" />
              Sign Out
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats */}
        {results.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-slate-600">Total Files</p>
                    <p className="text-slate-900 mt-1">{stats.total}</p>
                  </div>
                  <FileText className="w-8 h-8 text-slate-400" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-slate-600">Passed</p>
                    <p className="text-green-600 mt-1">{stats.passed}</p>
                  </div>
                  <CheckCircle2 className="w-8 h-8 text-green-400" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-slate-600">Warnings</p>
                    <p className="text-amber-600 mt-1">{stats.warnings}</p>
                  </div>
                  <AlertCircle className="w-8 h-8 text-amber-400" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-slate-600">Errors</p>
                    <p className="text-red-600 mt-1">{stats.errors}</p>
                  </div>
                  <XCircle className="w-8 h-8 text-red-400" />
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Upload Area */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle>Upload Charity Care Files</CardTitle>
            <CardDescription>
              Upload your charity care documentation files for validation. Accepted formats: PDF, Excel, CSV, XML
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`border-2 border-dashed rounded-lg p-12 text-center transition-all ${
                isDragging
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-slate-300 bg-slate-50 hover:border-slate-400'
              }`}
            >
              {isUploading ? (
                <div className="flex flex-col items-center gap-4">
                  <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
                  <p className="text-slate-600">Processing files...</p>
                </div>
              ) : (
                <>
                  <Upload className="w-12 h-12 text-slate-400 mx-auto mb-4" />
                  <p className="text-slate-700 mb-2">
                    Drag and drop files here, or click to browse
                  </p>
                  <p className="text-slate-500 mb-6">
                    Maximum file size: 10MB
                  </p>
                  <label htmlFor="file-upload">
                    <Button type="button" className="bg-blue-600 hover:bg-blue-700" asChild>
                      <span>
                        <FileText className="w-4 h-4 mr-2" />
                        Select Files
                      </span>
                    </Button>
                  </label>
                  <input
                    id="file-upload"
                    type="file"
                    multiple
                    onChange={handleFileInput}
                    className="hidden"
                    accept=".pdf,.xlsx,.xls,.csv,.xml"
                  />
                </>
              )}
            </div>

            <Alert className="mt-4 border-blue-200 bg-blue-50">
              <AlertCircle className="h-4 w-4 text-blue-600" />
              <AlertDescription className="text-blue-800">
                Ensure all patient data is de-identified before submission. Files are encrypted during transfer.
              </AlertDescription>
            </Alert>
          </CardContent>
        </Card>

        {/* Results Section */}
        {results.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Validation Results</CardTitle>
              <CardDescription>
                Review the validation status of your submitted files
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {results.map((result) => (
                <div
                  key={result.id}
                  className={`border rounded-lg p-4 ${getStatusColor(result.status)}`}
                >
                  <div className="flex items-start gap-4">
                    <div className="mt-0.5">{getStatusIcon(result.status)}</div>
                    <div className="flex-1">
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <p className="text-slate-900">{result.fileName}</p>
                          <p className="text-slate-600">
                            {result.uploadedAt.toLocaleString()}
                          </p>
                        </div>
                        <Badge
                          variant={result.status === 'pass' ? 'default' : 'secondary'}
                          className={
                            result.status === 'pass'
                              ? 'bg-green-600'
                              : result.status === 'warning'
                              ? 'bg-amber-600'
                              : 'bg-red-600'
                          }
                        >
                          {result.status.toUpperCase()}
                        </Badge>
                      </div>
                      <p className="text-slate-700 mb-2">{result.message}</p>
                      {result.details && result.details.length > 0 && (
                        <ul className="space-y-1">
                          {result.details.map((detail, idx) => (
                            <li key={idx} className="text-slate-600 flex items-start gap-2">
                              <span className="text-slate-400 mt-1">•</span>
                              <span>{detail}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
